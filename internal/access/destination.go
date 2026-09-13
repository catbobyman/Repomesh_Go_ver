package access

import (
	"context"
	"encoding/json"
	"strings"
	"unicode/utf8"
)

type Destination struct {
	canonical string
	home      bool
}

type ProjectDestination struct {
	Kind          string
	ProjectID     string
	OperationKind string
	OperationID   string
}

type ProjectDestinationResolver func(context.Context, string, ProjectDestination) (*string, error)

func (s *Service) SetProjectDestinationResolver(resolver ProjectDestinationResolver) {
	s.projectDestinationResolver = resolver
}

func (d Destination) ProjectDestination() (ProjectDestination, bool) {
	if d.canonical == "" || d.home {
		return ProjectDestination{}, false
	}
	var fields map[string]json.RawMessage
	if json.Unmarshal([]byte(d.canonical), &fields) != nil {
		return ProjectDestination{}, false
	}
	get := func(key string) string {
		var value string
		_ = json.Unmarshal(fields[key], &value)
		return value
	}
	result := ProjectDestination{Kind: get("kind"), ProjectID: get("projectId"), OperationKind: get("operationKind"), OperationID: get("operationId")}
	if result.Kind == "project" || result.Kind == "operation" && (result.OperationKind == "project_create" || result.OperationKind == "project_update") {
		return result, true
	}
	return ProjectDestination{}, false
}

func (s *Service) resolveProjectDestination(ctx context.Context, actor string, destination Destination) (*string, error) {
	target, ok := destination.ProjectDestination()
	if !ok || s.projectDestinationResolver == nil {
		return nil, nil
	}
	return s.projectDestinationResolver(ctx, actor, target)
}

func ParseDestination(data []byte) (Destination, error) {
	var fields map[string]json.RawMessage
	if json.Unmarshal(data, &fields) != nil || fields == nil {
		return Destination{}, failure(422, "VALIDATION_FAILED")
	}
	get := func(key string) string { var value string; _ = json.Unmarshal(fields[key], &value); return value }
	kind := get("kind")
	required := []string{"kind"}
	switch kind {
	case "home":
	case "project":
		required = append(required, "projectId")
	case "issue":
		required = append(required, "projectId", "issueId")
	case "conversation":
		required = append(required, "projectId", "conversationId")
	case "operation":
		required = append(required, "operationKind", "operationId")
		switch get("operationKind") {
		case "project_create", "provider_save", "model_test":
		case "project_update", "issue_create", "model_apply":
			required = append(required, "projectId")
		default:
			return Destination{}, failure(422, "VALIDATION_FAILED")
		}
	default:
		return Destination{}, failure(422, "VALIDATION_FAILED")
	}
	if len(fields) != len(required) {
		return Destination{}, failure(422, "VALIDATION_FAILED")
	}
	for _, key := range required {
		value := get(key)
		if value == "" || !utf8.ValidString(value) || utf8.RuneCountInString(value) > 128 || value == "." || value == ".." || strings.ContainsAny(value, "/%\\?#\x00") {
			return Destination{}, failure(422, "VALIDATION_FAILED")
		}
		for _, c := range value {
			if c < 32 || c == 127 {
				return Destination{}, failure(422, "VALIDATION_FAILED")
			}
		}
	}
	canonical, _ := json.Marshal(fields)
	return Destination{canonical: string(canonical), home: kind == "home"}, nil
}
