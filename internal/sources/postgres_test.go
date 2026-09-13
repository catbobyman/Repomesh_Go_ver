//go:build unix

package sources

import (
	"context"
	"testing"
	"time"

	"repomesh.local/repomesh/internal/projects"
	"repomesh.local/repomesh/internal/testdb"
)

func TestPostgresImportReplayAndPinnedDefault(t *testing.T) {
	pool := testdb.Open(t)
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	t.Cleanup(cancel)
	if _, err := pool.Exec(ctx, `INSERT INTO repomesh_access.accounts(id,github_id,display_name) VALUES ('owner-1',9101,'Import owner')`); err != nil {
		t.Fatal(err)
	}
	principal, err := AuthenticateDeployment(ctx, pool)
	if err != nil {
		t.Fatal(err)
	}
	importer, err := NewImporter(pool, principal, projects.NewCatalogWriter())
	if err != nil {
		t.Fatal(err)
	}
	command, err := ParseImport([]byte(`{
		"schemaVersion":1,
		"importId":"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
		"environmentTemplates":[{"id":"tpl","version":"v1","executorPoolId":"pool","approvedTemplateDigest":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","networkPolicyRef":"net","resourceClassId":"class","enabled":true}],
		"executionProfiles":[{"id":"exec","version":"v1","ownerId":"owner-1","name":"执行","templateId":"tpl","templateVersion":"v1","workerConcurrency":2,"verificationGroupEnabled":false}],
		"defaultBindings":[{"kind":"execution","ownerId":"owner-1","profileId":"exec","profileVersion":"v1"}]
	}`))
	if err != nil {
		t.Fatal(err)
	}
	first, err := importer.Import(ctx, command)
	if err != nil || first.Replayed || first.Receipt.DefaultBindings[0].ProfileVersion != "v1" {
		t.Fatalf("first import: %+v %v", first, err)
	}
	second, err := importer.Import(ctx, command)
	if err != nil || !second.Replayed || second.Receipt.CommittedAt != first.Receipt.CommittedAt {
		t.Fatalf("replay: %+v %v", second, err)
	}
	var pinned string
	if err := pool.QueryRow(ctx, `SELECT pinned_version FROM repomesh_projects.defaults WHERE actor='owner-1' AND kind='execution'`).Scan(&pinned); err != nil || pinned != "v1" {
		t.Fatalf("pinned=%q %v", pinned, err)
	}
	conflicting := command
	conflicting.canonical = append([]byte(nil), command.canonical...)
	conflicting.canonical[len(conflicting.canonical)-2]++
	if _, err := importer.Import(ctx, conflicting); err == nil {
		t.Fatal("conflicting import accepted")
	}
	got, err := importer.Get(ctx, command.value.ImportID)
	if err != nil || got.ImportID != first.Receipt.ImportID {
		t.Fatalf("get: %+v %v", got, err)
	}
}
