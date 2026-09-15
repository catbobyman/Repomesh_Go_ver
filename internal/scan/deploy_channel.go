package scan

import (
	"errors"
	"io"
	"sort"
	"strings"

	"gopkg.in/yaml.v3"
)

// DeployChannel is mechanism ④ DEPLOY: deployment manifests naming which
// services a repository waits for (depends_on, Service selectors) and
// which services it itself deploys (compose names, workload app labels).
// Deployment references name *services*, resolved through the alias
// registry like BUILD/RUNTIME_CALL — self-declared, hence declared.
type DeployChannel struct{}

// NewDeployChannel returns the channel ready for RegisterChannel.
func NewDeployChannel() DeployChannel { return DeployChannel{} }

// Name is the channel id and the dedupe namespace for its evidence.
func (DeployChannel) Name() string { return "DEPLOY" }

// deployMaxFiles bounds upstream fetches per repository.
const deployMaxFiles = 10

// k8sWorkloadKinds whose app labels name the service this repo deploys;
// appLabelKeys are the legacy and recommended label conventions.
var (
	k8sWorkloadKinds = []string{"Deployment", "StatefulSet", "DaemonSet"}
	k8sAppLabelKeys  = []string{"app", "app.kubernetes.io/name"}
	// k8sManifestKeywords mark a YAML as a k8s manifest by filename;
	// deployDirNames are directories that conventionally hold manifests.
	k8sManifestKeywords = []string{"deployment", "statefulset", "daemonset", "service", "ingress"}
	deployDirNames      = []string{"k8s", "deploy", "deployments", "helm", "charts", "manifests"}
)

// isComposeFilename: docker-compose / compose manifests (*.yml/*.yaml).
func isComposeFilename(filename string) bool {
	name := strings.ToLower(basename(filename))
	return (strings.HasPrefix(name, "docker-compose") || strings.HasPrefix(name, "compose")) &&
		(strings.HasSuffix(name, ".yml") || strings.HasSuffix(name, ".yaml"))
}

// isDeployFilename: compose by name; other manifests must be YAML and
// either carry a k8s keyword in the filename or live under a deployment
// directory. Helm values*.yaml are excluded — chart-specific data, not
// dependency signals.
func isDeployFilename(filename, path string) bool {
	name := strings.ToLower(basename(filename))
	if isComposeFilename(name) {
		return true
	}
	if strings.HasPrefix(name, "values") {
		return false
	}
	if !strings.HasSuffix(name, ".yaml") && !strings.HasSuffix(name, ".yml") {
		return false
	}
	for _, segment := range strings.Split(strings.ToLower(path), "/") {
		for _, dir := range deployDirNames {
			if segment == dir {
				return true
			}
		}
	}
	for _, keyword := range k8sManifestKeywords {
		if strings.Contains(name, keyword) {
			return true
		}
	}
	return false
}

// Select picks deployment manifests anywhere in the tree, sorted, capped.
func (DeployChannel) Select(tree []FileEntry) []string {
	var found []string
	for _, entry := range tree {
		if !entry.IsDir && isDeployFilename(entry.Path, entry.Path) {
			found = append(found, entry.Path)
		}
	}
	sort.Strings(found)
	if len(found) > deployMaxFiles {
		found = found[:deployMaxFiles]
	}
	return found
}

// Parse dispatches by filename: compose manifests by name, everything else
// by k8s kind inspection. Unknown content contributes nothing. Never fails.
func (DeployChannel) Parse(filename, content string) ChannelOutput {
	output := ChannelOutput{}
	targets, identities := parseDeployFile(basename(filename), content)
	for _, target := range targets {
		output.Evidence = append(output.Evidence, DepEvidence{
			Name:       target,
			Mechanism:  MechanismDeploy,
			Confidence: ConfidenceDeclared,
		})
	}
	output.DeployIdentities = identities
	return output
}

// parseDeployFile returns (targets, deploy identities).
func parseDeployFile(base, content string) ([]string, []string) {
	if isComposeFilename(base) {
		return parseCompose(content)
	}
	return parseK8s(content)
}

// parseCompose: every services.<name> is an identity this repository
// deploys; every depends_on entry (short list or long dict form) is a
// reference to another service.
func parseCompose(content string) ([]string, []string) {
	var targets, identities []string
	seenTargets := map[string]bool{}
	seenIdentities := map[string]bool{}

	for _, document := range yamlDocuments(content) {
		services, ok := document["services"].(map[string]any)
		if !ok {
			continue
		}
		for serviceName, spec := range services {
			appendUniqueString(&identities, seenIdentities, serviceName)
			specMap, ok := spec.(map[string]any)
			if !ok {
				continue
			}
			for _, dep := range dependsOnNames(specMap["depends_on"]) {
				appendUniqueString(&targets, seenTargets, dep)
			}
		}
	}
	return targets, identities
}

// dependsOnNames: depends_on as a list of names or a long-syntax dict →
// names. A ${...} placeholder names no concrete service and is skipped.
func dependsOnNames(value any) []string {
	var names []string
	switch typed := value.(type) {
	case []any:
		for _, item := range typed {
			if name, ok := item.(string); ok {
				names = append(names, name)
			}
		}
	case map[string]any:
		for name := range typed {
			names = append(names, name)
		}
	default:
		return nil
	}
	kept := make([]string, 0, len(names))
	for _, name := range names {
		trimmed := strings.TrimSpace(name)
		if trimmed != "" && !strings.Contains(trimmed, "$") {
			kept = append(kept, trimmed)
		}
	}
	return kept
}

// parseK8s: Deployment/StatefulSet/DaemonSet workloads contribute their
// app label as an identity; a Service contributes metadata.name as an
// identity and its spec.selector app value as a target — the Service
// fronts that app. Multi-document streams handled.
func parseK8s(content string) ([]string, []string) {
	var targets, identities []string
	seenTargets := map[string]bool{}
	seenIdentities := map[string]bool{}

	for _, document := range yamlDocuments(content) {
		switch kind, _ := document["kind"].(string); kind {
		case "Deployment", "StatefulSet", "DaemonSet":
			if label := workloadAppLabel(document); label != "" {
				appendUniqueString(&identities, seenIdentities, label)
			}
		case "Service":
			if name := metadataName(document); name != "" {
				appendUniqueString(&identities, seenIdentities, name)
			}
			if selector := serviceSelectorApp(document); selector != "" {
				appendUniqueString(&targets, seenTargets, selector)
			}
		}
	}
	return targets, identities
}

// workloadAppLabel reads spec.template.metadata.labels first (the pod
// labels, which is what selectors actually match), then metadata.labels.
func workloadAppLabel(document map[string]any) string {
	if labels := nested(document, "spec", "template", "metadata", "labels"); labels != nil {
		if value := labelValue(labels); value != "" {
			return value
		}
	}
	return labelValue(nested(document, "metadata", "labels"))
}

func serviceSelectorApp(document map[string]any) string {
	return labelValue(nested(document, "spec", "selector"))
}

// labelValue: a concrete app value from a labels/selector mapping.
func labelValue(labels any) string {
	table, ok := labels.(map[string]any)
	if !ok {
		return ""
	}
	for _, key := range k8sAppLabelKeys {
		value, ok := table[key].(string)
		if !ok {
			continue
		}
		value = strings.TrimSpace(value)
		if value != "" && !strings.Contains(value, "$") {
			return value
		}
	}
	return ""
}

func metadataName(document map[string]any) string {
	metadata, ok := nested(document, "metadata").(map[string]any)
	if !ok {
		return ""
	}
	name, ok := metadata["name"].(string)
	if !ok {
		return ""
	}
	name = strings.TrimSpace(name)
	if name == "" || strings.Contains(name, "$") {
		return ""
	}
	return name
}

// nested descends a dict path, guarding non-dict nodes along the way.
func nested(document map[string]any, path ...string) any {
	var node any = document
	for _, part := range path {
		table, ok := node.(map[string]any)
		if !ok {
			return nil
		}
		node = table[part]
	}
	return node
}

// ---------------------------------------------------------------------------
// shared YAML helpers
// ---------------------------------------------------------------------------

// yamlDocuments parses a multi-document YAML stream into dict documents.
// Never executes code and never fails: a malformed stream yields nil.
func yamlDocuments(content string) []map[string]any {
	decoder := yaml.NewDecoder(strings.NewReader(content))
	var documents []map[string]any
	for {
		var document any
		if err := decoder.Decode(&document); err != nil {
			if !errors.Is(err, io.EOF) {
				return nil
			}
			break
		}
		if table, ok := document.(map[string]any); ok {
			documents = append(documents, table)
		}
	}
	return documents
}

func appendUniqueString(items *[]string, seen map[string]bool, value string) {
	trimmed := strings.TrimSpace(value)
	if trimmed == "" {
		return
	}
	key := strings.ToLower(trimmed)
	if seen[key] {
		return
	}
	seen[key] = true
	*items = append(*items, trimmed)
}
