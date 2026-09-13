// Package web serves the browser API, frontend and process diagnostics.
package web

import (
	"context"
	"crypto/tls"
	"encoding/json"
	"errors"
	"fmt"
	"io/fs"
	"log/slog"
	"net"
	"net/http"
	"os"
	"path"
	"strings"
	"time"

	"repomesh.local/repomesh/internal/access"
	"repomesh.local/repomesh/internal/buildinfo"
)

func Run(ctx context.Context, addr, assets string) error {
	return RunAuthenticated(ctx, addr, assets, Auth{}, "", "")
}

func RunAuthenticated(ctx context.Context, addr, assets string, auth Auth, certFile, keyFile string) error {
	return RunConfigured(ctx, addr, assets, auth, Projects{}, Models{}, certFile, keyFile)
}

func RunConfigured(ctx context.Context, addr, assets string, auth Auth, projectAPI Projects, modelAPI Models, certFile, keyFile string) error {
	root := os.DirFS(assets)
	if info, err := fs.Stat(root, "index.html"); err != nil || info.IsDir() {
		return fmt.Errorf("frontend index.html missing in %q; run npm --prefix web ci and npm --prefix web run build", assets)
	}
	var certificate tls.Certificate
	var err error
	if certFile != "" || keyFile != "" {
		certificate, err = tls.LoadX509KeyPair(certFile, keyFile)
		if err != nil {
			return errors.New("cannot load HTTPS certificate and key")
		}
	}
	listener, err := net.Listen("tcp", addr)
	if err != nil {
		return fmt.Errorf("listen: %w", err)
	}
	if certFile != "" {
		listener = tls.NewListener(listener, &tls.Config{MinVersion: tls.VersionTLS12, Certificates: []tls.Certificate{certificate}})
	}
	server := &http.Server{
		Handler:           handlerConfigured(root, auth, projectAPI, modelAPI),
		ReadHeaderTimeout: 5 * time.Second,
		IdleTimeout:       60 * time.Second,
		WriteTimeout:      30 * time.Second,
	}
	slog.Info("web listening", "address", listener.Addr().String(), "version", buildinfo.Version, "authentication_configured", auth.Service != nil, "business_ready", false)
	return serve(ctx, server, listener)
}

func serve(ctx context.Context, server *http.Server, listener net.Listener) error {
	defer listener.Close()
	result := make(chan error, 1)
	go func() { result <- server.Serve(listener) }()
	var err error
	select {
	case err = <-result:
	case <-ctx.Done():
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		// Shutdown closes the listener before draining requests. Wait for the
		// drain itself, not just Serve, before allowing main to exit.
		if shutdownErr := server.Shutdown(shutdownCtx); shutdownErr != nil {
			_ = server.Close()
			<-result
			return fmt.Errorf("graceful shutdown: %w", shutdownErr)
		}
		err = <-result
	}
	if err != nil && !errors.Is(err, http.ErrServerClosed) {
		return err
	}
	return nil
}

func newHandler(assets fs.FS) http.Handler {
	return handlerWithAuth(assets, Auth{})
}

func handlerWithAuth(assets fs.FS, auth Auth) http.Handler {
	return handlerConfigured(assets, auth, Projects{}, Models{})
}

func handlerConfigured(assets fs.FS, auth Auth, projectAPI Projects, modelAPI Models) http.Handler {
	mux := http.NewServeMux()
	registerAuth(mux, auth)
	registerProjects(mux, auth, projectAPI)
	registerModels(mux, auth, modelAPI)
	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, map[string]any{
			"process": "repomesh-web", "version": buildinfo.Version,
			"status": "scaffold", "businessReady": false,
		})
	})
	mux.HandleFunc("GET /readyz", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusServiceUnavailable, map[string]string{
			"status": "not_implemented", "message": "Business capabilities are not implemented.",
		})
	})
	fileServer := http.FileServerFS(assets)
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/api" || strings.HasPrefix(r.URL.Path, "/api/") {
			writeJSON(w, http.StatusNotFound, map[string]string{"error": "not_implemented"})
			return
		}
		if r.Method != http.MethodGet && r.Method != http.MethodHead {
			w.Header().Set("Allow", "GET, HEAD")
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}
		name := strings.TrimPrefix(path.Clean(r.URL.Path), "/")
		if r.URL.Path == "/login" || strings.HasPrefix(r.URL.Path, "/auth/result/") && access.ValidID(strings.TrimPrefix(r.URL.Path, "/auth/result/")) || projectBrowserRoute(r.URL.Path) || modelBrowserRoute(r.URL.Path) {
			w.Header().Set("Cache-Control", "no-store")
			w.Header().Set("Referrer-Policy", "no-referrer")
			r = r.Clone(r.Context())
			r.URL.Path = "/"
			name = "index.html"
		}
		if name == "" {
			name = "index.html"
		}
		info, err := fs.Stat(assets, name)
		if err != nil || info.IsDir() {
			http.NotFound(w, r)
			return
		}
		fileServer.ServeHTTP(w, r)
	})
	return mux
}

func writeJSON(w http.ResponseWriter, status int, body any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.Header().Set("Cache-Control", "no-store")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(body)
}
