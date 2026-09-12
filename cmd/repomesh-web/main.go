package main

import (
	"context"
	"errors"
	"flag"
	"fmt"
	"io"
	"os"
	"os/signal"
	"syscall"
	"time"

	"repomesh.local/repomesh/internal/buildinfo"
	"repomesh.local/repomesh/internal/database"
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
	flags := flag.NewFlagSet("repomesh-web", flag.ContinueOnError)
	flags.SetOutput(stderr)
	addr := flags.String("addr", envOr("REPOMESH_WEB_ADDR", "127.0.0.1:8080"), "HTTP listen address")
	assets := flags.String("assets", envOr("REPOMESH_WEB_ASSETS", "web/dist"), "built frontend directory (relative to working directory)")
	version := flags.Bool("version", false, "print release version and exit")
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
	if err := web.Run(ctx, *addr, *assets); err != nil {
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
