package scan

import (
	"context"
	"encoding/json"
	"errors"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// PostgresCatalog stores repository cards in repomesh_scan.repositories.
// The AutoCard payload in the metadata column is written and read only via
// autoCardPayload/autoCardFromPayload — the single serializer.
type PostgresCatalog struct {
	pool *pgxpool.Pool
}

func NewPostgresCatalog(pool *pgxpool.Pool) *PostgresCatalog {
	return &PostgresCatalog{pool: pool}
}

const cardColumns = `id, name, url, description, topics, languages,
	fingerprint, profiled_at, metadata, test_commands, test_paths`

func (c *PostgresCatalog) Add(ctx context.Context, card RepositoryCard) error {
	payload, err := json.Marshal(cardMetadata(card.AutoCard))
	if err != nil {
		return err
	}
	_, err = c.pool.Exec(ctx, `
		INSERT INTO repomesh_scan.repositories
		    (id, name, url, description, topics, languages,
		     fingerprint, profiled_at, metadata, test_commands, test_paths)
		VALUES ($1, $2, $3, $4, $5, $6, $7, now(), $8, $9, $10)`,
		card.ID, card.Name, card.URL, card.Description,
		jsonSlice(card.Topics), jsonSlice(card.Languages),
		card.Fingerprint, payload, jsonSlice(card.TestCommands), jsonSlice(card.TestPaths))
	return err
}

func (c *PostgresCatalog) List(ctx context.Context) ([]RepositoryCard, error) {
	rows, err := c.pool.Query(ctx,
		`SELECT `+cardColumns+` FROM repomesh_scan.repositories ORDER BY name`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	cards := []RepositoryCard{}
	for rows.Next() {
		card, err := scanCard(rows)
		if err != nil {
			return nil, err
		}
		cards = append(cards, *card)
	}
	return cards, rows.Err()
}

func (c *PostgresCatalog) Get(ctx context.Context, id string) (*RepositoryCard, error) {
	card, err := c.queryCard(ctx,
		`SELECT `+cardColumns+` FROM repomesh_scan.repositories WHERE id = $1`, id)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	return card, err
}

func (c *PostgresCatalog) GetByName(ctx context.Context, name string) (*RepositoryCard, error) {
	card, err := c.queryCard(ctx,
		`SELECT `+cardColumns+` FROM repomesh_scan.repositories WHERE name = $1`, name)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	return card, err
}

// UpdateAutoCard whole-replaces the scan-derived card: metadata and
// fingerprint change, operator-owned fields do not. Idempotent.
func (c *PostgresCatalog) UpdateAutoCard(ctx context.Context, id string, card AutoCard, languages []string, fingerprint string) error {
	payload, err := json.Marshal(autoCardPayload(card))
	if err != nil {
		return err
	}
	tag, err := c.pool.Exec(ctx, `
		UPDATE repomesh_scan.repositories
		SET metadata = $2, languages = $3, fingerprint = $4, profiled_at = now()
		WHERE id = $1`, id, payload, jsonSlice(languages), fingerprint)
	if err != nil {
		return err
	}
	if tag.RowsAffected() == 0 {
		return pgx.ErrNoRows
	}
	return nil
}

func (c *PostgresCatalog) queryCard(ctx context.Context, sql string, args ...any) (*RepositoryCard, error) {
	row := c.pool.QueryRow(ctx, sql, args...)
	card, err := scanCard(row)
	if err != nil {
		return nil, err
	}
	return card, nil
}

type rowScanner interface{ Scan(dest ...any) error }

func scanCard(row rowScanner) (*RepositoryCard, error) {
	var (
		card                                     RepositoryCard
		topics, langs, commands, paths, metadata []byte
		profiledAt                               time.Time
	)
	if err := row.Scan(&card.ID, &card.Name, &card.URL, &card.Description,
		&topics, &langs, &card.Fingerprint, &profiledAt,
		&metadata, &commands, &paths); err != nil {
		return nil, err
	}
	card.Topics = jsonToSlice(topics)
	card.Languages = jsonToSlice(langs)
	card.TestCommands = jsonToSlice(commands)
	card.TestPaths = jsonToSlice(paths)
	card.ProfiledAt = profiledAt.UTC().Format(time.RFC3339)

	var payload map[string]any
	if err := json.Unmarshal(metadata, &payload); err != nil {
		return nil, err
	}
	card.AutoCard = autoCardFromPayload(payload)
	return &card, nil
}

func cardMetadata(card *AutoCard) map[string]any {
	if card == nil {
		return map[string]any{}
	}
	return autoCardPayload(*card)
}

func jsonSlice(values []string) []byte {
	if values == nil {
		values = []string{}
	}
	encoded, err := json.Marshal(values)
	if err != nil { // unreachable for []string
		return []byte("[]")
	}
	return encoded
}

func jsonToSlice(raw []byte) []string {
	var values []string
	if err := json.Unmarshal(raw, &values); err != nil || values == nil {
		return []string{}
	}
	return values
}
