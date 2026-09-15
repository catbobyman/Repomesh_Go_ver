package main

import (
	"context"
	"errors"
	"flag"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"repomesh.local/repomesh/internal/access"
	"repomesh.local/repomesh/internal/buildinfo"
	"repomesh.local/repomesh/internal/database"
	"repomesh.local/repomesh/internal/models"
	"repomesh.local/repomesh/internal/projects"
	"repomesh.local/repomesh/internal/reposcan"
	"repomesh.local/repomesh/internal/scan"
	"repomesh.local/repomesh/internal/web"
)

func main() {
	os.Exit(mainExit())
}

func mainExit() int {
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	return run(ctx, os.Args[1:], os.Stdout, os.Stderr)
}

func run(ctx context.Context, args []string, stdout, stderr io.Writer) int {
	if len(args) > 0 && args[0] == "db" {
		return runDatabase(ctx, args[1:], stdout, stderr)
	}
	if len(args) > 0 && args[0] == "sources" {
		return runSources(ctx, args[1:], stdout, stderr)
	}
	flags := flag.NewFlagSet("repomesh-web", flag.ContinueOnError)
	flags.SetOutput(stderr)
	addr := flags.String("addr", envOr("REPOMESH_WEB_ADDR", "127.0.0.1:8080"), "HTTP listen address")
	assets := flags.String("assets", envOr("REPOMESH_WEB_ASSETS", "web/dist"), "built frontend directory (relative to working directory)")
	version := flags.Bool("version", false, "print release version and exit")
	authConfig := flags.String("auth-config", os.Getenv("REPOMESH_AUTH_CONFIG"), "authentication deployment JSON file")
	if err := flags.Parse(args); err != nil {
		if errors.Is(err, flag.ErrHelp) {
			return 0
		}
		return 2
	}
	if *version {
		fmt.Fprintf(stdout, "repomesh-web %s\n", buildinfo.Version)
		return 0
	}
	if flags.NArg() != 0 {
		fmt.Fprintln(stderr, "unexpected positional arguments")
		return 2
	}
	var auth web.Auth
	var projectAPI web.Projects
	var modelAPI web.Models
	var scanAPI web.Scan
	var certFile, keyFile string
	if *authConfig != "" {
		startup, cancel := context.WithTimeout(ctx, 30*time.Second)
		runtime, err := access.OpenRuntime(startup, *authConfig, os.Getenv("REPOMESH_DATABASE_URL"))
		cancel()
		if err != nil {
			fmt.Fprintln(stderr, "authentication startup:", err)
			return 1
		}
		defer runtime.Close()
		auth = web.Auth{Service: runtime.Service, Origin: runtime.Deployment.Origin}
		projectService := projects.New(runtime.Pool(), runtime.Service)
		runtime.Service.SetProjectDestinationResolver(projectService.ResolveDestination)
		projectAPI = web.Projects{Service: projectService}
		catalog := projects.NewCatalogWriter()
		modelService := models.New(runtime.Pool(), runtime.Service, runtime.SecretStore(), catalog)
		runtime.Service.SetModelSaveDestinationResolver(modelService.ResolveDestination)
		modelAPI = web.Models{Service: modelService}
		certFile, keyFile = runtime.Deployment.TLSCertificateFile, runtime.Deployment.TLSKeyFile

		// Scan block: repository scanning + scope selection (D5/D8, design
		// doc 仓库扫描终版设计). Fetcher per platform via the router; the
		// catalog lives in the same PostgreSQL database.
		scanCatalog := scan.NewPostgresCatalog(runtime.Pool())
		scanService := scan.New(scan.Config{
			ScopeAssistEnabled: envBool("REPOMESH_SCOPE_ASSIST_ENABLED", true),
		}, scanCatalog)
		for _, channel := range scan.DefaultChannels() {
			scanService.RegisterChannel(channel)
		}
		fetcher := &reposcan.Router{
			GitHub: &reposcan.GitHubFetcher{Token: os.Getenv("REPOMESH_REPOSITORY_SCAN_GITHUB_TOKEN")},
			GitLab: &reposcan.GitLabFetcher{Token: os.Getenv("REPOMESH_REPOSITORY_SCAN_GITLAB_TOKEN")},
			Extra:  parsePlatformMap(os.Getenv("REPOMESH_REPOSITORY_SCAN_PLATFORMS")),
		}
		scanAPI = web.Scan{API: &scan.HTTP{
			Service:       scanService,
			Store:         scanCatalog,
			Runner:        &scan.Runner{Fetcher: fetcher, Store: scanCatalog, IncludeForks: envBool("REPOMESH_REPOSITORY_SCAN_INCLUDE_FORKS", false)},
			Jobs:          scan.NewJobRegistry(),
			Suggester:     scan.KeywordSuggester{Store: scanCatalog},
			Fetcher:       fetcher,
			Allowlist:     splitList(os.Getenv("REPOMESH_REPOSITORY_SCAN_ALLOWED_HOSTS")),
			PlatformExtra: parsePlatformMap(os.Getenv("REPOMESH_REPOSITORY_SCAN_PLATFORMS")),
			Authenticate: func(r *http.Request) error {
				if r.Method == http.MethodGet {
					return nil // reads stay open, matching the other catalog reads
				}
				if runtime.Deployment.Origin == "" || r.Header.Get("Origin") != runtime.Deployment.Origin {
					return errors.New("origin rejected")
				}
				_, err := runtime.Service.AuthenticateProjectRequest(
					r.Context(), web.SessionCookie(r), r.Header.Get("X-CSRF-Token"), true)
				return err
			},
		}}
	}
	if err := web.RunConfigured(ctx, *addr, *assets, auth, projectAPI, modelAPI, scanAPI, certFile, keyFile); err != nil {
		fmt.Fprintln(stderr, "web stopped:", err)
		return 1
	}
	return 0
}

func runDatabase(ctx context.Context, args []string, stdout, stderr io.Writer) int {
	if len(args) == 1 && (args[0] == "--help" || args[0] == "-h") {
		fmt.Fprintln(stdout, "Usage: repomesh-web db <check|migrate> [--database-url CONNECTION] [--timeout 30s]")
		fmt.Fprintln(stdout, "The connection defaults to REPOMESH_DATABASE_URL. Only migrate changes the schema.")
		return 0
	}
	if len(args) == 0 || args[0] != "check" && args[0] != "migrate" {
		fmt.Fprintln(stderr, "expected db check or db migrate; use db --help")
		return 2
	}
	command := args[0]
	flags := flag.NewFlagSet("repomesh-web db "+command, flag.ContinueOnError)
	flags.SetOutput(io.Discard)
	databaseURL := flags.String("database-url", "", "PostgreSQL connection string (defaults to REPOMESH_DATABASE_URL)")
	timeout := flags.Duration("timeout", 30*time.Second, "total connection and operation timeout")
	if err := flags.Parse(args[1:]); err != nil {
		if errors.Is(err, flag.ErrHelp) {
			fmt.Fprintf(stdout, "Usage: repomesh-web db %s [options]\n", command)
			flags.SetOutput(stdout)
			flags.PrintDefaults()
			return 0
		}
		fmt.Fprintln(stderr, "invalid database command arguments; use db "+command+" --help")
		return 2
	}
	if flags.NArg() != 0 || *timeout <= 0 {
		fmt.Fprintln(stderr, "database commands require valid flags and a positive timeout")
		return 2
	}
	hasURLFlag := false
	flags.Visit(func(value *flag.Flag) {
		if value.Name == "database-url" {
			hasURLFlag = true
		}
	})
	if !hasURLFlag {
		*databaseURL = os.Getenv("REPOMESH_DATABASE_URL")
	}
	ctx, cancel := context.WithTimeout(ctx, *timeout)
	defer cancel()
	db, err := database.Open(ctx, *databaseURL)
	if err != nil {
		fmt.Fprintln(stderr, err)
		if errors.Is(err, database.ErrInvalidConfig) {
			return 2
		}
		return 1
	}
	defer db.Close()
	var state database.SchemaState
	if command == "check" {
		state, err = db.Check(ctx)
	} else {
		state, err = db.Migrate(ctx)
	}
	if err != nil {
		fmt.Fprintln(stderr, err)
		return 1
	}
	status := "current"
	if state.Current == 0 {
		status = "missing"
	} else if state.Pending != 0 {
		status = "pending"
	}
	fmt.Fprintf(stdout, "schema status=%s current=%d target=%d pending=%d\n", status, state.Current, state.Target, state.Pending)
	if command == "check" && state.Pending != 0 {
		return 1
	}
	return 0
}

func envOr(name, fallback string) string {
	if value := os.Getenv(name); value != "" {
		return value
	}
	return fallback
}

func envBool(name string, fallback bool) bool {
	switch strings.ToLower(strings.TrimSpace(os.Getenv(name))) {
	case "1", "true", "yes", "on":
		return true
	case "0", "false", "no", "off":
		return false
	}
	return fallback
}

func splitList(value string) []string {
	var items []string
	for _, item := range strings.Split(value, ",") {
		if trimmed := strings.TrimSpace(item); trimmed != "" {
			items = append(items, trimmed)
		}
	}
	return items
}

func parsePlatformMap(value string) map[string]string {
	mapping := map[string]string{}
	for _, pair := range strings.Split(value, ",") {
		if host, platform, found := strings.Cut(strings.TrimSpace(pair), "="); found {
			mapping[strings.ToLower(host)] = strings.ToLower(platform)
		}
	}
	return mapping
}
