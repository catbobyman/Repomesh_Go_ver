package tasks

import (
	"context"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"

	"repomesh.local/repomesh/internal/decisionchain"
	"repomesh.local/repomesh/internal/testdb"
)

// chainSink adapts internal/decisionchain to tasks.DecisionSink — the same
// composition the server assembly uses: 梯子、窗口与重规划共用一条决策链。
type chainSink struct {
	chain *decisionchain.PostgresStore
}

func (s chainSink) RecordPlanRevised(ctx context.Context, tx pgx.Tx, e PlanRevisedEvent) error {
	_, err := s.chain.RecordPlanRevisedInTx(ctx, tx, decisionchain.Event{
		Requirement: e.RequirementText, Actor: e.Actor,
		IdempotencyKey: e.IdempotencyKey, RepositoryIDs: e.AffectedRepositories,
		Accepted: true, Status: decisionchain.StatusAdjusted, UpstreamRef: e.UpstreamRef,
	})
	return err
}

func (s chainSink) RecordFeedback(ctx context.Context, e FeedbackEvent) (string, time.Time, error) {
	node, err := s.chain.RecordFeedback(ctx, decisionchain.Event{
		Requirement: e.RequirementText, Actor: e.ReporterID,
		IdempotencyKey: e.IdempotencyKey, RepositoryIDs: e.AffectedRepositories,
		Accepted: false, Status: decisionchain.DecisionStatus(e.Status),
		UpstreamRef: e.UpstreamRef, Rationale: e.Reason,
		ContextRef: map[string]any{"role": string(e.Role), "sourceIds": e.AffectedRepositories},
	})
	if err != nil {
		return "", time.Time{}, err
	}
	return node.ID, node.CreatedAt, nil
}

func (s chainSink) BlockedSince(ctx context.Context, requirementKey string, since time.Time) ([]BlockedFeedback, error) {
	nodes, err := s.chain.BlockedSince(ctx, requirementKey, since)
	if err != nil {
		return nil, err
	}
	out := make([]BlockedFeedback, 0, len(nodes))
	for _, node := range nodes {
		role, _ := node.ContextRef["role"].(string)
		out = append(out, BlockedFeedback{
			NodeID: node.ID, ReporterID: node.ActorID, Role: role,
			Reason: node.Rationale, UpstreamRef: node.ParentNodeID,
			AffectedRepositories: node.AffectedRepositories, CreatedAt: node.CreatedAt,
		})
	}
	return out, nil
}

func TestEscalationLadderAndCollectionWindow(t *testing.T) {
	pool := testdb.Open(t)
	store := NewPostgresStore(pool)
	svc := &EscalationService{
		Store:  store,
		Sink:   chainSink{chain: decisionchain.NewPostgresStore(pool)},
		Window: 50 * time.Millisecond,
	}
	ctx := context.Background()

	_, project := seedOrgProject(t, pool)
	plan, err := store.CreatePlan(ctx, PlanWrite{
		ProjectID:       project,
		RequirementText: "为项目选择合适的仓库并完成改造",
		RequirementKey:  decisionchain.RequirementKey("为项目选择合适的仓库并完成改造"),
		Batches:         [][]string{{"gateway"}, {"sdk"}},
		DAG:             map[string][]string{"sdk": {"gateway"}},
	})
	if err != nil {
		t.Fatal(err)
	}

	// 两个 Worker 各报一条 BLOCKED。
	first, firstAt, err := svc.ReportBlocked(ctx, BlockedReport{PlanID: plan.ID, ReporterID: "worker-1",
		Role: RoleWorker, Reason: "要改的文件在 SDK 仓库",
		AffectedRepositories: []string{"gateway", "sdk"}})
	if err != nil {
		t.Fatal(err)
	}
	second, _, err := svc.ReportBlocked(ctx, BlockedReport{PlanID: plan.ID, ReporterID: "worker-2",
		Role: RoleWorker, Reason: "依赖缺失", AffectedRepositories: []string{"sdk"}})
	if err != nil {
		t.Fatal(err)
	}

	// TM 消化第二条（closed，不出现在收集结果），升级第一条（blocked，上游指 w1）。
	if err := svc.ResolveWithinRepo(ctx, plan.ID, second, "tm-gateway", "本仓可消化"); err != nil {
		t.Fatal(err)
	}
	escalated, _, err := svc.ReportBlocked(ctx, BlockedReport{PlanID: plan.ID, ReporterID: "tm-gateway",
		Role: RoleTM, Reason: "确认超范围，需重规划",
		AffectedRepositories: []string{"gateway", "sdk"}, UpstreamRef: first})
	if err != nil {
		t.Fatal(err)
	}

	feedback, err := svc.MarkDeprecatedAndCollect(ctx, plan.ID, firstAt)
	if err != nil {
		t.Fatal(err)
	}

	planAfter, err := store.GetPlan(ctx, plan.ID)
	if err != nil {
		t.Fatal(err)
	}
	if planAfter.ReplanState != ReplanStateDeprecated {
		t.Fatalf("plan replan_state = %q, want deprecated", planAfter.ReplanState)
	}

	// 收集的是梯子末梢：TM 升级节点 + 未升级的 worker-2 并发反馈（30 秒窗
	// 合并语义）；w1 原节点作为被升级的父节点剔除；被消化的 closed 节点不出现。
	if len(feedback) != 2 {
		t.Fatalf("ladder leaves = %d (%+v), want 2", len(feedback), feedback)
	}
	ids := map[string]BlockedFeedback{}
	for _, f := range feedback {
		ids[f.NodeID] = f
	}
	esc, ok := ids[escalated]
	if !ok || esc.Role != string(RoleTM) {
		t.Fatalf("TM escalation leaf missing: %+v", feedback)
	}
	if _, ok := ids[second]; !ok {
		t.Fatalf("concurrent worker-2 feedback missing: %+v", feedback)
	}
	if _, ok := ids[first]; ok {
		t.Fatal("escalated parent must be replaced by its child")
	}

	// 双轴挂钩照常工作：同一 plan 上走一次重规划，决策链落 adjusted 节点。
	rev, err := store.ApplyRevision(ctx, RevisionCommand{
		PlanID: plan.ID, ExpectedVersion: "v1",
		NewBatches: [][]string{{"gateway"}, {"sdk", "third"}},
		NewTasks: []TaskSnapshot{
			{TaskUID: "gateway-fix", RepositoryID: "gateway", Title: "网关改造"},
			{TaskUID: "third-migrate", RepositoryID: "third", Title: "新增接入"},
		},
		DAG:   map[string][]string{"third": {"gateway"}},
		Actor: "leader", Reason: "收集窗后局部重排",
		UpstreamRef:    escalated,
		IdempotencyKey: "rev-ladder-1",
	})
	if err != nil {
		t.Fatal(err)
	}
	if rev.CreatedTasks != 2 || rev.SupersededTasks != 0 {
		t.Fatalf("revision migration = created %d superseded %d, want 2/0", rev.CreatedTasks, rev.SupersededTasks)
	}
}
