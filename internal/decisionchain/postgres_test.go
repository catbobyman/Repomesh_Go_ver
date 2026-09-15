package decisionchain

import (
	"context"
	"errors"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"

	"repomesh.local/repomesh/internal/testdb"
)

func TestPostgresRecordIdempotentAndVersioned(t *testing.T) {
	pool := testdb.Open(t)
	store := NewPostgresStore(pool)
	ctx := context.Background()

	base := nodeWrite{
		RequirementText:      "为项目选择合适的仓库",
		RequirementKey:       RequirementKey("为项目选择合适的仓库"),
		Step:                 StepConfirmation,
		Status:               StatusConfirmed,
		ActorID:              "xiaochen",
		Action:               "范围圈定确认",
		Rationale:            "为项目选择合适的仓库",
		ContextRef:           map[string]any{"sourceIds": []string{"card-1"}},
		AffectedRepositories: []string{"ts-common", "ts-api"},
		Source:               SourceEvent,
	}

	first := base
	first.EventID = "evt-1"
	stored, err := store.Record(ctx, first)
	if err != nil {
		t.Fatal(err)
	}
	if stored.ID == "" || stored.Version != 1 || stored.ActorType != "human" {
		t.Fatalf("unexpected first node: %+v", stored)
	}
	if len(stored.AffectedRepositories) != 2 || stored.ContextRef["sourceIds"] == nil {
		t.Fatalf("json columns lost in round trip: %+v", stored)
	}

	// Idempotent redelivery: same event_id returns the stored row untouched.
	again := base
	again.EventID = "evt-1"
	again.Status = StatusRejected
	reread, err := store.Record(ctx, again)
	if err != nil {
		t.Fatal(err)
	}
	if reread.ID != stored.ID || reread.Status != StatusConfirmed {
		t.Fatalf("redelivery must return the original row: %+v", reread)
	}

	// Same requirement, new event: version bumps to 2.
	second := base
	second.EventID = "evt-2"
	v2, err := store.Record(ctx, second)
	if err != nil {
		t.Fatal(err)
	}
	if v2.Version != 2 {
		t.Fatalf("second event version = %d, want 2", v2.Version)
	}
}

func TestPostgresGetList(t *testing.T) {
	pool := testdb.Open(t)
	store := NewPostgresStore(pool)
	ctx := context.Background()

	key := RequirementKey("列表检索用需求")
	w := nodeWrite{
		EventID: "evt-list-1", RequirementText: "列表检索用需求", RequirementKey: key,
		Step: StepConfirmation, Status: StatusConfirmed, ActorID: "u1",
		Action: "范围圈定确认", Rationale: "r", ContextRef: map[string]any{},
		AffectedRepositories: []string{"repo-a", "repo-b"}, Source: SourceEvent,
	}
	node, err := store.Record(ctx, w)
	if err != nil {
		t.Fatal(err)
	}

	got, err := store.Get(ctx, node.ID)
	if err != nil || got == nil || got.ID != node.ID {
		t.Fatalf("Get failed: %v", err)
	}
	if _, err := store.Get(ctx, NewUUIDv4()); !errors.Is(err, pgx.ErrNoRows) {
		t.Fatalf("missing id = %v, want ErrNoRows", err)
	}

	byRepo, err := store.List(ctx, Filter{Repository: "repo-b", Limit: 10})
	if err != nil || len(byRepo) != 1 {
		t.Fatalf("filter by repository: %d hits, err %v", len(byRepo), err)
	}
	none, err := store.List(ctx, Filter{Repository: "repo-zzz", Limit: 10})
	if err != nil || len(none) != 0 {
		t.Fatalf("unmatched repository filter: %d hits, err %v", len(none), err)
	}
	byKey, err := store.List(ctx, Filter{RequirementKey: key})
	if err != nil || len(byKey) != 1 {
		t.Fatalf("filter by key: %d hits, err %v", len(byKey), err)
	}
}

func TestPostgresFeatureSettings(t *testing.T) {
	pool := testdb.Open(t)
	store := NewPostgresStore(pool)
	ctx := context.Background()

	// Seeded row is on; an unknown feature counts as on (D12).
	on, err := store.FeatureEnabled(ctx, "decision_chain")
	if err != nil || !on {
		t.Fatalf("seeded toggle = %v, err %v", on, err)
	}
	if on, _ := store.FeatureEnabled(ctx, "no_such_feature"); !on {
		t.Fatal("missing feature row must count as enabled")
	}

	if err := store.SetFeature(ctx, "decision_chain", false, "xiaochen", time.Now()); err != nil {
		t.Fatal(err)
	}
	if on, _ := store.FeatureEnabled(ctx, "decision_chain"); on {
		t.Fatal("toggle off did not persist")
	}
	if err := store.SetFeature(ctx, "decision_chain", true, "xiaochen", time.Now()); err != nil {
		t.Fatal(err)
	}
}
