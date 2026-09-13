//go:build unix

package sources

import (
	"context"
	"errors"
	"strings"
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

func TestPostgresImportRelistedOlderVersionKeepsHead(t *testing.T) {
	pool := testdb.Open(t)
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	t.Cleanup(cancel)
	if _, err := pool.Exec(ctx, `INSERT INTO repomesh_access.accounts(id,github_id,display_name) VALUES ('owner-1',9101,'Import owner'),('owner-2',9102,'Other owner')`); err != nil {
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
	const template = `{"id":"tpl","version":"v1","executorPoolId":"pool","approvedTemplateDigest":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","networkPolicyRef":"net","resourceClassId":"class","enabled":true}`
	const v1 = `{"id":"exec","version":"v1","ownerId":"owner-1","name":"执行 v1","templateId":"tpl","templateVersion":"v1","workerConcurrency":2,"verificationGroupEnabled":false}`
	const v2 = `{"id":"exec","version":"v2","ownerId":"owner-1","name":"执行 v2","templateId":"tpl","templateVersion":"v1","workerConcurrency":4,"verificationGroupEnabled":true}`
	manifest := func(importID, profiles, pinned string) ImportCommand {
		command, parseErr := ParseImport([]byte(`{"schemaVersion":1,"importId":"` + importID + `","environmentTemplates":[` + template + `],"executionProfiles":[` + profiles + `],"defaultBindings":[{"kind":"execution","ownerId":"owner-1","profileId":"exec","profileVersion":"` + pinned + `"}]}`))
		if parseErr != nil {
			t.Fatal(parseErr)
		}
		return command
	}
	head := func() (string, string, string) {
		var version, name, pinned string
		if err := pool.QueryRow(ctx, `SELECT p.current_version,p.name,d.pinned_version FROM repomesh_projects.profiles p
			JOIN repomesh_projects.defaults d ON d.kind=p.kind AND d.profile_id=p.id AND d.actor='owner-1'
			WHERE p.kind='execution' AND p.id='exec'`).Scan(&version, &name, &pinned); err != nil {
			t.Fatal(err)
		}
		return version, name, pinned
	}
	if _, err := importer.Import(ctx, manifest("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1", v1, "v1")); err != nil {
		t.Fatal(err)
	}
	if version, name, pinned := head(); version != "v1" || name != "执行 v1" || pinned != "v1" {
		t.Fatalf("after v1 import head=%q name=%q pinned=%q", version, name, pinned)
	}
	if _, err := importer.Import(ctx, manifest("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa2", v1+","+v2, "v2")); err != nil {
		t.Fatal(err)
	}
	if version, name, pinned := head(); version != "v2" || name != "执行 v2" || pinned != "v2" {
		t.Fatalf("after v2 import head=%q name=%q pinned=%q", version, name, pinned)
	}
	relisted, err := importer.Import(ctx, manifest("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa3", v1, "v1"))
	if err != nil || relisted.Replayed || relisted.Receipt.DefaultBindings[0].ProfileVersion != "v1" {
		t.Fatalf("relist v1: %+v %v", relisted, err)
	}
	if version, name, pinned := head(); version != "v2" || name != "执行 v2" || pinned != "v1" {
		t.Fatalf("after relisting v1 head=%q name=%q pinned=%q", version, name, pinned)
	}
	var versions int
	if err := pool.QueryRow(ctx, `SELECT count(*) FROM repomesh_projects.profile_versions WHERE kind='execution' AND profile_id='exec'`).Scan(&versions); err != nil || versions != 2 {
		t.Fatalf("profile versions=%d %v", versions, err)
	}
	changed := strings.Replace(v1, `"workerConcurrency":2`, `"workerConcurrency":3`, 1)
	_, err = importer.Import(ctx, manifest("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa4", changed, "v1"))
	var conflict *Failure
	if !errors.As(err, &conflict) || conflict.Code != "EXECUTION_CONFLICT" {
		t.Fatalf("same version different content: %v", err)
	}
	var imports int
	if err := pool.QueryRow(ctx, `SELECT count(*) FROM repomesh_sources.imports`).Scan(&imports); err != nil || imports != 3 {
		t.Fatalf("imports after conflict=%d %v", imports, err)
	}
	if version, _, pinned := head(); version != "v2" || pinned != "v1" {
		t.Fatalf("conflict changed catalog head=%q pinned=%q", version, pinned)
	}
	stolen := strings.Replace(v2, `"ownerId":"owner-1"`, `"ownerId":"owner-2"`, 1)
	_, err = importer.Import(ctx, manifest("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa5", stolen, "v2"))
	var owner *projects.Failure
	if !errors.As(err, &owner) || owner.Code != "PROFILE_OWNER_CONFLICT" {
		t.Fatalf("other owner re-listing exec: %v", err)
	}
	var profileOwner string
	if err := pool.QueryRow(ctx, `SELECT owner FROM repomesh_projects.profiles WHERE kind='execution' AND id='exec'`).Scan(&profileOwner); err != nil || profileOwner != "owner-1" {
		t.Fatalf("profile owner after rejected import=%q %v", profileOwner, err)
	}
}
