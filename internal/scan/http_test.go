package scan

import (
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
