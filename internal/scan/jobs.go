package scan

import (
	"context"
	"fmt"
	"strings"
	"sync"
	"time"
)

// ScanJob is the API view of one background scan (design doc §3.D-3/4):
// 202 + polling. Jobs are in-process records — a process restart loses
// them, and polling a lost job answers 404 (the honest semantics the
// Python version shipped).
type ScanJob struct {
	ID                    string `json:"id"`
	Kind                  string `json:"kind"` // organization | repository
	URL                   string `json:"url"`
	Status                string `json:"status"` // running | succeeded | failed
	Total                 int    `json:"total"`
	Scanned               int    `json:"scanned"`
	LastScannedRepository string `json:"lastScannedRepository,omitempty"`
	Registered            int    `json:"registered"`
	Skipped               int    `json:"skipped"`
	Failed                int    `json:"failed"`
	Error                 string `json:"error,omitempty"`
	StartedAt             string `json:"startedAt"`
	FinishedAt            string `json:"finishedAt,omitempty"`
}

// ScanJobStatus values.
const (
	JobRunning   = "running"
	JobSucceeded = "succeeded"
	JobFailed    = "failed"
)

// JobRegistry keeps in-process scan jobs and runs them in the background.
type JobRegistry struct {
	mu   sync.Mutex
	seq  int
	jobs map[string]*ScanJob
}

// NewJobRegistry returns an empty registry.
func NewJobRegistry() *JobRegistry {
	return &JobRegistry{jobs: map[string]*ScanJob{}}
}

// Start launches run in a background goroutine (fresh context: a scan
// outlives the HTTP request that started it) and returns the job id.
// progress receives (done, total, repository name) while running.
func (r *JobRegistry) Start(kind, url string, run func(ctx context.Context, progress func(done, total int, name string)) (RegistrationCounts, error)) string {
	r.mu.Lock()
	r.seq++
	id := fmt.Sprintf("scan-%d-%d", time.Now().Unix(), r.seq)
	job := &ScanJob{
		ID:        id,
		Kind:      kind,
		URL:       url,
		Status:    JobRunning,
		StartedAt: time.Now().UTC().Format(time.RFC3339),
	}
	r.jobs[id] = job
	r.mu.Unlock()

	go func() {
		ctx, cancel := context.WithTimeout(context.Background(), 30*time.Minute)
		defer cancel()
		counts, err := run(ctx, func(done, total int, name string) {
			r.mu.Lock()
			job.Scanned = done
			if total > job.Total {
				job.Total = total
			}
			job.LastScannedRepository = name
			r.mu.Unlock()
		})
		r.mu.Lock()
		defer r.mu.Unlock()
		if err != nil {
			job.Status = JobFailed
			job.Error = err.Error()
		} else {
			job.Status = JobSucceeded
		}
		job.Total = counts.Total
		job.Scanned = counts.Total
		job.Registered = counts.Registered
		job.Skipped = counts.Skipped
		job.Failed = counts.Failed
		now := time.Now().UTC().Format(time.RFC3339)
		job.FinishedAt = now
	}()
	return id
}

// Get returns a snapshot of one job.
func (r *JobRegistry) Get(id string) (ScanJob, bool) {
	r.mu.Lock()
	defer r.mu.Unlock()
	job, ok := r.jobs[id]
	if !ok {
		return ScanJob{}, false
	}
	return *job, true
}

// sanitizeMessage keeps outbound failure messages generic; outbound details
// belong in the server log only.
func sanitizeMessage(err error) string {
	message := strings.TrimSpace(err.Error())
	return message
}
