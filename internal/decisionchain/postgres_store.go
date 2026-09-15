package decisionchain

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
	"github.com/jackc/pgx/v5/pgxpool"
)

// PostgresStore implements Store on the shared pool. Tables and columns are
// owned by migration 0008 (改动清单); the shapes there are authoritative.
type PostgresStore struct {
	pool *pgxpool.Pool
}

// NewPostgresStore builds the store (composition root only).
func NewPostgresStore(pool *pgxpool.Pool) *PostgresStore { return &PostgresStore{pool: pool} }

const nodeColumns = `id, event_id, requirement_text, requirement_key,
  COALESCE(project_id::text, ''), COALESCE(parent_node_id::text, ''),
  step, version, status, actor_type, actor_id, action, rationale,
  context_ref, affected_repositories, source, created_at`

func scanNode(row pgx.Row) (DecisionNode, error) {
	var (
		n                     DecisionNode
		eventID               *string
		contextRef, repos     []byte
	)
	if err := row.Scan(&n.ID, &eventID, &n.RequirementText, &n.RequirementKey,
		&n.ProjectID, &n.ParentNodeID, &n.Step, &n.Version, &n.Status,
		&n.ActorType, &n.ActorID, &n.Action, &n.Rationale,
		&contextRef, &repos, &n.Source, &n.CreatedAt); err != nil {
		return DecisionNode{}, err
	}
	if eventID != nil {
		n.EventID = *eventID
	}
	n.ContextRef = map[string]any{}
	if len(contextRef) > 0 {
		if err := json.Unmarshal(contextRef, &n.ContextRef); err != nil {
			return DecisionNode{}, fmt.Errorf("decode context_ref: %w", err)
		}
	}
	n.AffectedRepositories = []string{}
	if len(repos) > 0 {
		if err := json.Unmarshal(repos, &n.AffectedRepositories); err != nil {
			return DecisionNode{}, fmt.Errorf("decode affected_repositories: %w", err)
		}
	}
	return n, nil
}

// Record inserts one node; idempotent by event_id, versioned per
// (requirement_key, step) with a single retry against the unique index (F9).
func (p *PostgresStore) Record(ctx context.Context, w nodeWrite) (DecisionNode, error) {
	node, err := p.recordOnce(ctx, w)
	if isUniqueViolation(err) {
		// Concurrent confirmation of the same requirement: re-read max(version).
		node, err = p.recordOnce(ctx, w)
	}
	return node, err
}

func (p *PostgresStore) recordOnce(ctx context.Context, w nodeWrite) (DecisionNode, error) {
	tx, err := p.pool.Begin(ctx)
	if err != nil {
		return DecisionNode{}, err
	}
	defer tx.Rollback(ctx)

	var version int
	if err := tx.QueryRow(ctx,
		`SELECT COALESCE(MAX(version), 0) + 1 FROM public.decision_chain_nodes
		 WHERE requirement_key = $1 AND step = $2`, w.RequirementKey, string(w.Step),
	).Scan(&version); err != nil {
		return DecisionNode{}, err
	}

	contextRef, err := json.Marshal(w.ContextRef)
	if err != nil {
		return DecisionNode{}, fmt.Errorf("encode context_ref: %w", err)
	}
	if contextRef == nil {
		contextRef = []byte("{}")
	}
	repos, err := json.Marshal(w.AffectedRepositories)
	if err != nil {
		return DecisionNode{}, fmt.Errorf("encode affected_repositories: %w", err)
	}
	if repos == nil {
		repos = []byte("[]")
	}

	id := NewUUIDv4()
	tag, err := tx.Exec(ctx, `
		INSERT INTO public.decision_chain_nodes (
		  id, event_id, requirement_text, requirement_key, actor_type, actor_id,
		  action, rationale, context_ref, step, version, status,
		  affected_repositories, source
		) VALUES ($1, $2, $3, $4, 'human', $5, $6, $7, $8, $9, $10, $11, $12, $13)
		ON CONFLICT (event_id) WHERE event_id IS NOT NULL DO NOTHING`,
		id, w.EventID, w.RequirementText, w.RequirementKey, w.ActorID,
		w.Action, w.Rationale, contextRef, string(w.Step), version,
		string(w.Status), repos, string(w.Source))
	if err != nil {
		return DecisionNode{}, err
	}

	var stored DecisionNode
	if tag.RowsAffected() == 0 {
		// Idempotent redelivery: return the already-stored node unchanged.
		stored, err = p.byEventID(ctx, tx, w.EventID)
	} else {
		stored, err = p.byID(ctx, tx, id)
	}
	if err != nil {
		return DecisionNode{}, err
	}
	return stored, tx.Commit(ctx)
}

func (p *PostgresStore) byEventID(ctx context.Context, tx pgx.Tx, eventID string) (DecisionNode, error) {
	row := tx.QueryRow(ctx,
		`SELECT `+nodeColumns+` FROM public.decision_chain_nodes WHERE event_id = $1 LIMIT 1`, eventID)
	return scanNode(row)
}

func (p *PostgresStore) byID(ctx context.Context, tx pgx.Tx, id string) (DecisionNode, error) {
	row := tx.QueryRow(ctx,
		`SELECT `+nodeColumns+` FROM public.decision_chain_nodes WHERE id = $1`, id)
	return scanNode(row)
}

// Get reads one node by id; pgx.ErrNoRows when absent.
func (p *PostgresStore) Get(ctx context.Context, id string) (*DecisionNode, error) {
	row := p.pool.QueryRow(ctx,
		`SELECT `+nodeColumns+` FROM public.decision_chain_nodes WHERE id = $1`, id)
	node, err := scanNode(row)
	if err != nil {
		return nil, err
	}
	return &node, nil
}

// List applies the filter; newest first.
func (p *PostgresStore) List(ctx context.Context, f Filter) ([]DecisionNode, error) {
	where := []string{"true"}
	args := []any{}
	if f.RequirementKey != "" {
		args = append(args, f.RequirementKey)
		where = append(where, fmt.Sprintf("requirement_key = $%d", len(args)))
	}
	if f.Step != nil && *f.Step != "" {
		args = append(args, string(*f.Step))
		where = append(where, fmt.Sprintf("step = $%d", len(args)))
	}
	if f.Repository != "" {
		args = append(args, f.Repository)
		where = append(where, fmt.Sprintf("affected_repositories ? $%d", len(args)))
	}
	if f.Keyword != "" {
		args = append(args, "%"+f.Keyword+"%")
		where = append(where, fmt.Sprintf("requirement_text ILIKE $%d", len(args)))
	}
	limit := f.Limit
	if limit <= 0 {
		limit = 50
	}
	if limit > 200 {
		limit = 200
	}
	args = append(args, limit, f.Offset)
	rows, err := p.pool.Query(ctx, `SELECT `+nodeColumns+` FROM public.decision_chain_nodes
		WHERE `+strings.Join(where, " AND ")+`
		ORDER BY created_at DESC LIMIT $`+strconv.Itoa(len(args)-1)+` OFFSET $`+strconv.Itoa(len(args)),
		args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	nodes := []DecisionNode{}
	for rows.Next() {
		node, err := scanNode(rows)
		if err != nil {
			return nil, err
		}
		nodes = append(nodes, node)
	}
	return nodes, rows.Err()
}

// PendingEmbeddings returns nodes whose embedding row is missing or was made
// with a different model (F5 model-mix guard).
func (p *PostgresStore) PendingEmbeddings(ctx context.Context, model string, limit int) ([]DecisionNode, error) {
	rows, err := p.pool.Query(ctx, `SELECT `+nodeColumns+`
		FROM public.decision_chain_nodes n
		LEFT JOIN public.decision_embeddings e ON e.node_id = n.id
		WHERE e.node_id IS NULL OR e.model <> $1
		ORDER BY n.created_at
		LIMIT $2`, model, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	nodes := []DecisionNode{}
	for rows.Next() {
		node, err := scanNode(rows)
		if err != nil {
			return nil, err
		}
		nodes = append(nodes, node)
	}
	return nodes, rows.Err()
}

// UpsertEmbedding writes the vector row: primary vector column and JSON
// fallback copy in one statement (D11 double write).
func (p *PostgresStore) UpsertEmbedding(ctx context.Context, nodeID, model string, vec []float32, embeddedAt time.Time) error {
	encoded, err := json.Marshal(vec)
	if err != nil {
		return fmt.Errorf("encode embedding: %w", err)
	}
	tag, err := p.pool.Exec(ctx, `
		INSERT INTO public.decision_embeddings (id, node_id, embedding, model, embedding_vec, embedded_at)
		VALUES (gen_random_uuid(), $1, $2::jsonb, $3, $4::public.vector, $5)
		ON CONFLICT (node_id) DO UPDATE SET
		  embedding = EXCLUDED.embedding,
		  model = EXCLUDED.model,
		  embedding_vec = EXCLUDED.embedding_vec,
		  embedded_at = EXCLUDED.embedded_at`,
		nodeID, encoded, model, formatVector(vec), embeddedAt)
	if err != nil {
		return err
	}
	if tag.RowsAffected() == 0 {
		return pgx.ErrNoRows
	}
	return nil
}

// SemanticCandidates orders current-model embeddings by cosine distance to
// the query vector (pgvector HNSW path); score = 1 - distance.
func (p *PostgresStore) SemanticCandidates(ctx context.Context, model string, query []float32, limit int) ([]ScoredNode, error) {
	rows, err := p.pool.Query(ctx, `SELECT `+nodeColumns+`,
		  1 - (e.embedding_vec OPERATOR(public.<=>) $2::public.vector) AS score
		FROM public.decision_chain_nodes n
		JOIN public.decision_embeddings e ON e.node_id = n.id
		WHERE e.model = $1 AND e.embedding_vec IS NOT NULL
		ORDER BY e.embedding_vec OPERATOR(public.<=>) $2::public.vector
		LIMIT $3`, model, formatVector(query), limit)
	if err != nil {
		return nil, err
	}
	return collectScored(rows)
}

// StructuralCandidates prescreens nodes sharing any of the given repository
// names via the GIN index; scoring (Jaccard) is the caller's job.
func (p *PostgresStore) StructuralCandidates(ctx context.Context, names []string, limit int) ([]DecisionNode, error) {
	if len(names) == 0 {
		return nil, nil
	}
	rows, err := p.pool.Query(ctx, `SELECT `+nodeColumns+`
		FROM public.decision_chain_nodes
		WHERE affected_repositories ?| $1::text[]
		ORDER BY created_at DESC
		LIMIT $2`, names, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	nodes := []DecisionNode{}
	for rows.Next() {
		node, err := scanNode(rows)
		if err != nil {
			return nil, err
		}
		nodes = append(nodes, node)
	}
	return nodes, rows.Err()
}

// FeatureEnabled returns the toggle; a missing row counts as enabled (D12).
func (p *PostgresStore) FeatureEnabled(ctx context.Context, feature string) (bool, error) {
	var enabled bool
	err := p.pool.QueryRow(ctx,
		`SELECT enabled FROM public.feature_settings WHERE feature = $1`, feature).Scan(&enabled)
	if errors.Is(err, pgx.ErrNoRows) {
		return true, nil
	}
	return enabled, err
}

// SetFeature writes the toggle with its audit fields.
func (p *PostgresStore) SetFeature(ctx context.Context, feature string, enabled bool, updatedBy string, at time.Time) error {
	tag, err := p.pool.Exec(ctx, `
		INSERT INTO public.feature_settings (feature, enabled, updated_by, updated_at)
		VALUES ($1, $2, $3, $4)
		ON CONFLICT (feature) DO UPDATE SET
		  enabled = EXCLUDED.enabled,
		  updated_by = EXCLUDED.updated_by,
		  updated_at = EXCLUDED.updated_at`,
		feature, enabled, updatedBy, at)
	if err != nil {
		return err
	}
	if tag.RowsAffected() == 0 {
		return pgx.ErrNoRows
	}
	return nil
}

func collectScored(rows pgx.Rows) ([]ScoredNode, error) {
	defer rows.Close()
	hits := []ScoredNode{}
	for rows.Next() {
		var (
			n                 DecisionNode
			eventID           *string
			contextRef, repos []byte
			score             float64
		)
		if err := rows.Scan(&n.ID, &eventID, &n.RequirementText, &n.RequirementKey,
			&n.ProjectID, &n.ParentNodeID, &n.Step, &n.Version, &n.Status,
			&n.ActorType, &n.ActorID, &n.Action, &n.Rationale,
			&contextRef, &repos, &n.Source, &n.CreatedAt, &score); err != nil {
			return nil, err
		}
		if eventID != nil {
			n.EventID = *eventID
		}
		n.ContextRef = map[string]any{}
		if len(contextRef) > 0 {
			if err := json.Unmarshal(contextRef, &n.ContextRef); err != nil {
				return nil, fmt.Errorf("decode context_ref: %w", err)
			}
		}
		n.AffectedRepositories = []string{}
		if len(repos) > 0 {
			if err := json.Unmarshal(repos, &n.AffectedRepositories); err != nil {
				return nil, fmt.Errorf("decode affected_repositories: %w", err)
			}
		}
		hits = append(hits, ScoredNode{Node: n, Score: score})
	}
	return hits, rows.Err()
}

// formatVector renders a pgvector text literal: [1,2,3].
func formatVector(vec []float32) string {
	if len(vec) == 0 {
		return "[]"
	}
	buf := make([]byte, 0, len(vec)*8+2)
	buf = append(buf, '[')
	for i, v := range vec {
		if i > 0 {
			buf = append(buf, ',')
		}
		buf = strconv.AppendFloat(buf, float64(v), 'g', -1, 32)
	}
	return string(append(buf, ']'))
}

func isUniqueViolation(err error) bool {
	var pgErr *pgconn.PgError
	return errors.As(err, &pgErr) && pgErr.Code == "23505"
}
