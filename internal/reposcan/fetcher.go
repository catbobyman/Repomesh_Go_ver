package reposcan

import (
	"context"
	"errors"
	"sync"
)

// TreeEntry is one line of a repository file tree.
type TreeEntry struct {
	Path  string
	IsDir bool
}

// Fetcher supplies the three raw materials the scan pipeline consumes:
// the full file tree, the recent commit subjects, and individual file
// contents. Implementations talk to one hosting platform; they never
// parse repository content — that is the channels' job.
type Fetcher interface {
	// FetchTree lists every file and directory entry of the default branch.
	FetchTree(ctx context.Context, repoURL string) ([]TreeEntry, error)
	// FetchCommits returns at most limit recent commit subjects
	// (first line of the message), newest first.
	FetchCommits(ctx context.Context, repoURL string, limit int) ([]string, error)
	// FetchFileContent returns one file's text content. Implementations
	// return an error for missing or unreadable files; the pipeline
	// treats any error as "this channel sees nothing here".
	FetchFileContent(ctx context.Context, repoURL string, path string) (string, error)
}

// ErrUnauthorized reports the configured credential was rejected.
var ErrUnauthorized = errors.New("reposcan: credential rejected")

// ErrUnavailable reports the platform could not be reached or answered
// unusably. The pipeline degrades per item; only the entry points decide
// whether that becomes a whole-scan failure.
var ErrUnavailable = errors.New("reposcan: platform unavailable")

// Cache wraps a Fetcher with per-scan memoization. Several channels select
// overlapping files, so each distinct path must cost exactly one upstream
// call; a fetch that failed (or found nothing) is cached too — a later
// channel must not retry it.
type Cache struct {
	inner Fetcher

	mu          sync.Mutex
	tree        []TreeEntry
	treeDone    bool
	commits     []string
	commitsDone bool
	contents    map[string]cachedContent
}

type cachedContent struct {
	value string
	err   error
}

// NewCache memoizes every call to inner for the lifetime of the Cache.
// One Cache per scan.
func NewCache(inner Fetcher) *Cache {
	return &Cache{inner: inner, contents: make(map[string]cachedContent)}
}

// FetchTree implements Fetcher.
func (c *Cache) FetchTree(ctx context.Context, repoURL string) ([]TreeEntry, error) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if !c.treeDone {
		tree, err := c.inner.FetchTree(ctx, repoURL)
		if err != nil {
			return nil, err
		}
		c.tree = tree
		c.treeDone = true
	}
	return c.tree, nil
}

// FetchCommits implements Fetcher.
func (c *Cache) FetchCommits(ctx context.Context, repoURL string, limit int) ([]string, error) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if !c.commitsDone {
		commits, err := c.inner.FetchCommits(ctx, repoURL, limit)
		if err != nil {
			return nil, err
		}
		c.commits = commits
		c.commitsDone = true
	}
	if limit >= len(c.commits) {
		return c.commits, nil
	}
	return c.commits[:limit], nil
}

// FetchFileContent implements Fetcher. Errors are cached alongside values:
// a path that missed once stays a miss for the whole scan.
func (c *Cache) FetchFileContent(ctx context.Context, repoURL string, path string) (string, error) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if cached, seen := c.contents[path]; seen {
		return cached.value, cached.err
	}
	value, err := c.inner.FetchFileContent(ctx, repoURL, path)
	c.contents[path] = cachedContent{value: value, err: err}
	return value, err
}
