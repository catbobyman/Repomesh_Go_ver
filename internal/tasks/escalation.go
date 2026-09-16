package tasks

import (
	"context"
	"errors"
	"time"

	"github.com/jackc/pgx/v5"
)

// 升级梯子（协议 §2.1-2.3）：反馈统一落决策链（不建独立表）——
// worker 节点 → TM 升级节点（upstream 指 worker 节点）→ Leader 重规划节点
// （upstream 指 TM 节点）。梯子每一跳可溯；消化 = closed 节点。

// ErrUnknownPlan reports an escalation against a plan that does not exist.
var ErrUnknownPlan = errors.New("tasks: plan does not exist")

// FeedbackRole is who filed the feedback on the escalation ladder.
type FeedbackRole string

const (
	RoleWorker FeedbackRole = "worker"
	RoleTM     FeedbackRole = "tm"
	RoleLeader FeedbackRole = "leader"
)

// FeedbackEvent is one ladder hop: a blocked report (or a TM close).
type FeedbackEvent struct {
	RequirementText      string
	RequirementKey       string
	ReporterID           string
	Role                 FeedbackRole
	Reason               string
	AffectedRepositories []string
	UpstreamRef          string // 升级时指向上一跳节点；首跳为空
	Status               string // "blocked"（上报/升级）| "closed"（TM 消化）
	IdempotencyKey       string
}

// BlockedFeedback is one collected ladder leaf after the window.
type BlockedFeedback struct {
	NodeID               string    `json:"nodeId"`
	ReporterID           string    `json:"reporterId"`
	Role                 string    `json:"role"`
	Reason               string    `json:"reason"`
	UpstreamRef          string    `json:"upstreamRef,omitempty"`
	AffectedRepositories []string  `json:"affectedRepositories"`
	CreatedAt            time.Time `json:"createdAt"`
}

// DecisionSink gains the feedback ports: RecordFeedback (blocked/closed hop)
// and BlockedSince (window collection — ladder leaves only).
type DecisionSink interface {
	RecordPlanRevised(ctx context.Context, tx pgx.Tx, e PlanRevisedEvent) error
	RecordFeedback(ctx context.Context, e FeedbackEvent) (string, time.Time, error)
	BlockedSince(ctx context.Context, requirementKey string, since time.Time) ([]BlockedFeedback, error)
}

// EscalationService runs the ladder and the collection window. Window
// defaults to 30s (协议 §2 步骤 3); tests shrink it.
type EscalationService struct {
	Store  *PostgresStore
	Sink   DecisionSink
	Window time.Duration
	Now    func() time.Time
}

// ReportBlocked records one ladder hop and returns the decision node id
// plus its creation time — the id is the escalation's upstream handle and
// the time anchors the collection window (触发报告 = 窗口起点).
func (s *EscalationService) ReportBlocked(ctx context.Context, r BlockedReport) (string, time.Time, error) {
	plan, err := s.Store.GetPlan(ctx, r.PlanID)
	if errors.Is(err, pgx.ErrNoRows) {
		return "", time.Time{}, ErrUnknownPlan
	}
	if err != nil {
		return "", time.Time{}, err
	}
	key := r.IdempotencyKey
	if key == "" {
		key = newUUIDv4()
	}
	node, at, err := s.Sink.RecordFeedback(ctx, FeedbackEvent{
		RequirementText:      plan.RequirementText,
		RequirementKey:       plan.RequirementKey,
		ReporterID:           r.ReporterID,
		Role:                 r.Role,
		Reason:               r.Reason,
		AffectedRepositories: r.AffectedRepositories,
		UpstreamRef:          r.UpstreamRef,
		Status:               "blocked",
		IdempotencyKey:       key,
	})
	if err != nil {
		return "", time.Time{}, err
	}
	return node, at, nil
}

// BlockedReport is one escalation hop.
type BlockedReport struct {
	PlanID               string
	ReporterID           string
	Role                 FeedbackRole
	Reason               string
	AffectedRepositories []string
	UpstreamRef          string // 升级 hop 指向上一跳节点
	IdempotencyKey       string
}

// ResolveWithinRepo records the TM digest: the blocked report was solved
// inside the repository, ladder closed (append-only — the original node is
// never rewritten).
func (s *EscalationService) ResolveWithinRepo(ctx context.Context, planID, blockedNodeID, byTM, note string) error {
	plan, err := s.Store.GetPlan(ctx, planID)
	if err != nil {
		return err
	}
	if _, _, err := s.Sink.RecordFeedback(ctx, FeedbackEvent{
		RequirementText: plan.RequirementText,
		RequirementKey:  plan.RequirementKey,
		ReporterID:      byTM,
		Role:            RoleTM,
		Reason:          note,
		UpstreamRef:     blockedNodeID,
		Status:          "closed",
		IdempotencyKey:  newUUIDv4(),
	}); err != nil {
		return err
	}
	return nil
}

// MarkDeprecatedAndCollect opens the collection window anchored at since
// (the triggering report's time): plan → deprecated (在跑任务继续), wait
// Window merging concurrent feedback, then collect the ladder leaves —
// blocked nodes whose id no child escalation references.
func (s *EscalationService) MarkDeprecatedAndCollect(ctx context.Context, planID string, since time.Time) ([]BlockedFeedback, error) {
	if err := s.Store.MarkDeprecated(ctx, planID); err != nil {
		return nil, err
	}
	plan, err := s.Store.GetPlan(ctx, planID)
	if err != nil {
		return nil, err
	}

	window := s.Window
	if window <= 0 {
		window = 30 * time.Second
	}
	timer := time.NewTimer(window)
	defer timer.Stop()
	select {
	case <-ctx.Done():
		return nil, ctx.Err()
	case <-timer.C:
	}

	all, err := s.Sink.BlockedSince(ctx, plan.RequirementKey, since)
	if err != nil {
		return nil, err
	}
	return ladderLeaves(all), nil
}

func (s *EscalationService) now() time.Time {
	if s.Now != nil {
		return s.Now()
	}
	return time.Now()
}

// ladderLeaves drops every node that another collected node escalates
// (parents stay in the chain for audit; the leaves are what the Leader
// replans on).
func ladderLeaves(all []BlockedFeedback) []BlockedFeedback {
	parents := map[string]bool{}
	for _, f := range all {
		if f.UpstreamRef != "" {
			parents[f.UpstreamRef] = true
		}
	}
	leaves := make([]BlockedFeedback, 0, len(all))
	for _, f := range all {
		if !parents[f.NodeID] {
			leaves = append(leaves, f)
		}
	}
	return leaves
}
