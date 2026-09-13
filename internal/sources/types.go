package sources

import (
	"context"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	"repomesh.local/repomesh/internal/projects"
)

type EnvironmentTemplate struct {
	ID                     string `json:"id"`
	Version                string `json:"version"`
	ExecutorPoolID         string `json:"executorPoolId"`
	ApprovedTemplateDigest string `json:"approvedTemplateDigest"`
	NetworkPolicyRef       string `json:"networkPolicyRef"`
	ResourceClassID        string `json:"resourceClassId"`
	Enabled                bool   `json:"enabled"`
}

type ExecutionProfile struct {
	ID                       string `json:"id"`
	Version                  string `json:"version"`
	OwnerID                  string `json:"ownerId"`
	Name                     string `json:"name"`
	TemplateID               string `json:"templateId"`
	TemplateVersion          string `json:"templateVersion"`
	WorkerConcurrency        int    `json:"workerConcurrency"`
	VerificationGroupEnabled bool   `json:"verificationGroupEnabled"`
}

type DefaultBinding struct {
	Kind           string `json:"kind"`
	OwnerID        string `json:"ownerId"`
	ProfileID      string `json:"profileId"`
	ProfileVersion string `json:"profileVersion"`
}

type Manifest struct {
	SchemaVersion        int                  `json:"schemaVersion"`
	ImportID             string               `json:"importId"`
	EnvironmentTemplates []EnvironmentTemplate `json:"environmentTemplates"`
	ExecutionProfiles    []ExecutionProfile    `json:"executionProfiles"`
	DefaultBindings      []DefaultBinding      `json:"defaultBindings"`
}

type ImportCommand struct {
	value     Manifest
	canonical []byte
}

type VersionRef struct {
	ID      string `json:"id"`
	Version string `json:"version"`
}

type DefaultResult struct {
	OwnerID         string `json:"ownerId"`
	ProfileID       string `json:"profileId"`
	ProfileVersion  string `json:"profileVersion"`
	DefaultRevision string `json:"defaultRevision"`
}

type Receipt struct {
	ImportID             string          `json:"importId"`
	SchemaVersion        int             `json:"schemaVersion"`
	EnvironmentTemplates []VersionRef    `json:"environmentTemplates"`
	ExecutionProfiles    []VersionRef    `json:"executionProfiles"`
	DefaultBindings      []DefaultResult `json:"defaultBindings"`
	CommittedAt          time.Time       `json:"committedAt"`
}

type ImportResult struct {
	Receipt  Receipt
	Replayed bool
}

type DeploymentPrincipal struct {
	deploymentID string
	sessionUser  string
}

type Importer struct {
	pool      *pgxpool.Pool
	principal DeploymentPrincipal
	catalog   *projects.CatalogWriter
	hook      importHook
}

type Failure struct {
	Status int
	Code   string
}

func (e *Failure) Error() string { return e.Code }

type importPhase string

const (
	ownersLocked                importPhase = "owners_locked"
	importLocked                importPhase = "import_locked"
	templatesInserted           importPhase = "templates_inserted"
	executionProfilesInserted   importPhase = "execution_profiles_inserted"
	defaultsBound               importPhase = "defaults_bound"
	importReceiptInserted       importPhase = "import_receipt_inserted"
	importBeforeCommit          importPhase = "import_before_commit"
)

type importHook func(context.Context, importPhase) error

func failure(status int, code string) error { return &Failure{Status: status, Code: code} }
func unavailable() error                    { return failure(503, "RESULT_UNCONFIRMED") }
