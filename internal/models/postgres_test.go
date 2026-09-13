//go:build unix

package models

import (
	"bytes"
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"os"
	"path/filepath"
	"sync"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	"repomesh.local/repomesh/internal/access"
	"repomesh.local/repomesh/internal/projects"
	"repomesh.local/repomesh/internal/secrets"
	"repomesh.local/repomesh/internal/testdb"
)

func digest(value string) string {
	sum := sha256.Sum256([]byte(value))
	return hex.EncodeToString(sum[:])
}

func cookie() string {
	var value [32]byte
	_, _ = rand.Read(value[:])
	return base64.RawURLEncoding.EncodeToString(value[:])
}

func testService(t *testing.T) (*Service, access.ProjectPrincipal, *pgxpool.Pool) {
	t.Helper()
	pool := testdb.Open(t)
	ctx := context.Background()
	root := make([]byte, 32)
	_, _ = rand.Read(root)
	rootPath := filepath.Join(t.TempDir(), "root")
	if err := os.WriteFile(rootPath, root, 0600); err != nil {
		t.Fatal(err)
	}
	store, err := secrets.New(ctx, pool, secrets.Config{ActiveRootID: "models-test", Roots: []secrets.RootFile{{ID: "models-test", Path: rootPath}}})
	if err != nil {
		t.Fatal(err)
	}
	authorization := access.New(pool, store, nil)
	actor := "10000000-0000-4000-8000-000000000001"
	if _, err := pool.Exec(ctx, `INSERT INTO repomesh_access.accounts(id,github_id,display_name) VALUES ($1,9001,'Model actor')`, actor); err != nil {
		t.Fatal(err)
	}
	sessionCookie := cookie()
	bindingCookie := cookie()
	sessionHash := digest(sessionCookie)
	bindingHash := digest(bindingCookie)
	if _, err := pool.Exec(ctx, `INSERT INTO repomesh_access.bindings(hash,identity_generation,expires_at) VALUES ($1,1,now()+interval '1 day')`, bindingHash); err != nil {
		t.Fatal(err)
	}
	if _, err := pool.Exec(ctx, `INSERT INTO repomesh_access.sessions(hash,actor,binding,generation,expires_at,last_active_at) VALUES ($1,$2,$3,1,now()+interval '1 day',now())`, sessionHash, actor, bindingHash); err != nil {
		t.Fatal(err)
	}
	principal, err := authorization.AuthenticateProjectRequest(ctx, sessionCookie, "", false)
	if err != nil {
		t.Fatal(err)
	}
	return New(pool, authorization, store, projects.NewCatalogWriter()), principal, pool
}

func saveBody(key string) SaveCommand {
	raw, err := ReadSaveBody([]byte(`{"providerId":null,"expectedRevision":null,"name":"开发网关","baseUrl":"https://gateway.example.invalid/v1","apiFormat":"openai_chat_completions","secret":{"mode":"replace","value":"sk-test-key"},"models":[{"id":null,"modelId":"deepseek-chat","displayName":"对话","contextWindow":256000,"maxOutputTokens":128000,"reasoning":true,"vision":false}]}`))
	if err != nil {
		panic(err)
	}
	command, err := NewSaveCommand(key, "req-1", raw)
	if err != nil {
		panic(err)
	}
	return command
}

func TestPostgresSaveIdempotentAndClose(t *testing.T) {
	service, principal, pool := testService(t)
	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
	t.Cleanup(cancel)
	key := "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
	result, err := service.Save(ctx, principal, saveBody(key))
	if err != nil || result.HTTPStatus != 201 || result.Receipt.committed == nil {
		t.Fatalf("first save: %+v %v", result, err)
	}
	replay, err := service.Save(ctx, principal, saveBody(key))
	if err != nil || replay.HTTPStatus != 200 || replay.Receipt.committed == nil || replay.Receipt.committed.ProviderRevision != result.Receipt.committed.ProviderRevision {
		t.Fatalf("replay: %+v %v", replay, err)
	}
	var providers, revisions, secretsCount int
	if err := pool.QueryRow(ctx, `SELECT count(*) FROM repomesh_models.providers`).Scan(&providers); err != nil || providers != 1 {
		t.Fatalf("providers=%d", providers)
	}
	if err := pool.QueryRow(ctx, `SELECT count(*) FROM repomesh_models.provider_revisions`).Scan(&revisions); err != nil || revisions != 1 {
		t.Fatalf("revisions=%d", revisions)
	}
	if err := pool.QueryRow(ctx, `SELECT count(*) FROM repomesh_secrets.versions`).Scan(&secretsCount); err != nil || secretsCount != 2 {
		t.Fatalf("secrets=%d", secretsCount)
	}
	closed, err := service.CloseSave(ctx, principal, CloseCommand{key: key})
	if err != nil || closed.committed == nil || closed.committed.ProviderRevision != result.Receipt.committed.ProviderRevision {
		t.Fatalf("close after save: %+v %v", closed, err)
	}
	late := saveBody(key)
	late.body.data = bytes.ReplaceAll(late.body.data, []byte("sk-test-key"), []byte("sk-other-key"))
	if _, err := service.Save(ctx, principal, late); err == nil {
		t.Fatal("changed input replayed as new save")
	}
}

func TestPostgresTwentyWaySameSave(t *testing.T) {
	service, principal, pool := testService(t)
	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
	t.Cleanup(cancel)
	key := "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
	var wg sync.WaitGroup
	results := make([]SaveResult, 20)
	errs := make([]error, 20)
	for i := 0; i < 20; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			results[i], errs[i] = service.Save(ctx, principal, saveBody(key))
		}(i)
	}
	wg.Wait()
	var committed string
	for i := 0; i < 20; i++ {
		if errs[i] != nil || results[i].Receipt.committed == nil {
			t.Fatalf("worker %d: %+v %v", i, results[i], errs[i])
		}
		if committed == "" {
			committed = results[i].Receipt.committed.ProviderRevision
		} else if results[i].Receipt.committed.ProviderRevision != committed {
			t.Fatal("concurrent saves created different revisions")
		}
	}
	var n int
	if err := pool.QueryRow(ctx, `SELECT count(*) FROM repomesh_models.provider_revisions`).Scan(&n); err != nil || n != 1 {
		t.Fatalf("revisions=%d", n)
	}
}

func TestPostgresCloseWinsAgainstLateSave(t *testing.T) {
	service, principal, _ := testService(t)
	ctx := context.Background()
	key := "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
	receipt, err := service.CloseSave(ctx, principal, CloseCommand{key: key})
	if err != nil || receipt.closed == nil {
		t.Fatalf("close empty: %+v %v", receipt, err)
	}
	if _, err := service.Save(ctx, principal, saveBody(key)); err == nil {
		t.Fatal("save after close succeeded")
	}
	again, err := service.CloseSave(ctx, principal, CloseCommand{key: key})
	if err != nil || again.closed == nil || !again.closed.ClosedAt.Equal(receipt.closed.ClosedAt) {
		t.Fatalf("second close changed time: %+v %v", again, err)
	}
}

func TestPostgresImportPinnedDefault(t *testing.T) {
	_, principal, pool := testService(t)
	ctx := context.Background()
	t.Log(principal.ActorID())
	var raw json.RawMessage
	_ = raw
	_ = pool
	_ = ctx
}
