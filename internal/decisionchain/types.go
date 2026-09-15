// Package decisionchain is the 历史决策 module (design:
// docs/历史决策终版设计-Go蓝图与可开可关-2026-09-15.md, D9-D14). It stores
// decision nodes (scope confirmations first), embeds them for semantic
// recall with a structural fallback, and exposes read + toggle APIs.
//
// This file is the frozen contract skeleton of 方案清单 §8: signatures the
// host wiring (track B) compiles against. Implementation lands task by task.
package decisionchain

import (
	"context"
	"net/http"

	"github.com/jackc/pgx/v5/pgxpool"
)

// Event is the producer-side write shape (方案清单 §3 写路径①). One scope
// confirmation becomes one decision node with step=confirmation.
type Event struct {
	Requirement    string   // raw requirement text, normalized here
	Actor          string   // session username
	IdempotencyKey string   // producer idempotency key, stored as event_id
	RepositoryIDs  []string // selected repository ids, resolved to names here
	Accepted       bool     // true = confirmed, false = rejected
}

// Config is the module assembly; every field maps to a design decision.
type Config struct {
	// EmbeddingBaseURL empty = semantic recall off; recall degrades to
	// structural (D11/D12 semantics, mirrors the Python behavior).
	EmbeddingBaseURL string
	EmbeddingAPIKey  string
	// EmbeddingModel defaults to bge-m3; vectors are stored as vector(1024).
	EmbeddingModel string
	// ResolveName maps a repository id to its normalized name. ok=false keeps
	// the raw id in affected_repositories (F4: names first, ids as fallback).
	ResolveName func(ctx context.Context, id string) (name string, ok bool)
}

// Service assembles the decision chain module on the shared connection pool.
// The zero-value is unusable; build it with New.
type Service struct {
	pool *pgxpool.Pool
	cfg  Config
}

// New wires the module onto the shared pool (composition root only).
func New(cfg Config, pool *pgxpool.Pool) *Service {
	return &Service{pool: pool, cfg: cfg}
}

// Record persists one producer event as a decision node. Idempotent by
// Event.IdempotencyKey; a record failure must never fail the producer's own
// flow (F3 fail-open is the caller's policy, this method only reports).
func (s *Service) Record(ctx context.Context, e Event) error { return nil }

// Enabled reports the feature toggle (feature_settings row 'decision_chain',
// missing row counts as on).
func (s *Service) Enabled() bool { return true }

// RegisterRoutes mounts the 5 decision endpoints and the 2 toggle endpoints:
// GET /api/decision-chains, GET /api/decision-chains/{id},
// GET /api/decision-chains/similar, GET /api/decision-chains/semantic-search,
// POST /api/decision-chains/embeddings/refresh,
// GET|PUT /api/settings/decision-chain.
func (s *Service) RegisterRoutes(mux *http.ServeMux) {}
