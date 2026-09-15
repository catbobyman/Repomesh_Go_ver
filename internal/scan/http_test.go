package scan

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestScanJobCreateRejectsUnknownFields(t *testing.T) {
	handler := &HTTP{}
	recorder := httptest.NewRecorder()
	request := httptest.NewRequest("POST", "/api/scan-jobs",
		strings.NewReader(`{"kind":"repository","url":"https://github.com/acme/orders","githubToken":"leak"}`))
	handler.handleScanJobCreate(recorder, request)
	if recorder.Code != 400 {
		t.Fatalf("status = %d, want 400", recorder.Code)
	}
	if body := recorder.Body.String(); !strings.Contains(body, "githubToken") {
		t.Fatalf("the offending field must be named: %s", body)
	}
}

type suggesterFunc func(requirement string, limit int) ([]Suggestion, error)

func (f suggesterFunc) Suggest(requirement string, limit int) ([]Suggestion, error) {
	return f(requirement, limit)
}

// Production assembles the adapter with a composite literal (main.go), so
// NewHTTP cannot be relied on: route registration itself must seed the boot
// default from the service config, and a later PUT must still override it.
func TestScopeAssistSeededFromServiceConfigAtRegistration(t *testing.T) {
	suggest := suggesterFunc(func(requirement string, limit int) ([]Suggestion, error) {
		return []Suggestion{{RepositoryID: "r1"}}, nil
	})
	newRequest := func() *http.Request {
		return httptest.NewRequest("POST", "/api/scope/suggestions",
			strings.NewReader(`{"requirement":"add a billing export"}`))
	}

	on := &HTTP{Service: &Service{cfg: Config{ScopeAssistEnabled: true}}, Suggester: suggest}
	on.RegisterRoutes(http.NewServeMux())
	recorder := httptest.NewRecorder()
	on.handleScopeSuggestions(recorder, newRequest())
	if recorder.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200 with the config default on and no PUT: %s",
			recorder.Code, recorder.Body.String())
	}

	off := &HTTP{Service: &Service{}, Suggester: suggest}
	off.RegisterRoutes(http.NewServeMux())
	recorder = httptest.NewRecorder()
	off.handleScopeSuggestions(recorder, newRequest())
	if recorder.Code != http.StatusServiceUnavailable {
		t.Fatalf("status = %d, want 503 with the config default off", recorder.Code)
	}

	off.SetAssistEnabled(true)
	recorder = httptest.NewRecorder()
	off.handleScopeSuggestions(recorder, newRequest())
	if recorder.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200 after the runtime override", recorder.Code)
	}
}
