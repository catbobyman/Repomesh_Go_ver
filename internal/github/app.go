package github

import (
	"bytes"
	"context"
	"crypto"
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha256"
	"crypto/x509"
	"encoding/base64"
	"encoding/json"
	"encoding/pem"
	"errors"
	"net/http"
	"net/url"
	"strconv"
	"time"
)

func (c *Client) AppCapability(ctx context.Context, owner, name string) (Capability, error) {
	if !pathSegment(owner) || !pathSegment(name) {
		return Capability{}, &Error{Kind: "rejected"}
	}
	ctx, cancel := context.WithTimeout(ctx, requestTimeout)
	defer cancel()
	keyPEM, err := c.config.PrivateKey(ctx)
	if err != nil {
		return Capability{}, &Error{Kind: "unavailable"}
	}
	key, err := parsePrivateKey(keyPEM)
	if err != nil {
		return Capability{}, err
	}
	token, err := c.appToken(key)
	if err != nil {
		return Capability{}, err
	}
	target := "https://api.github.com/repos/" + url.PathEscape(owner) + "/" + url.PathEscape(name) + "/installation"
	payload, _, status, err := c.request(ctx, http.MethodGet, target, token, nil)
	observed := time.Now().UTC()
	if err != nil {
		var failure *Error
		if status == http.StatusNotFound && errors.As(err, &failure) && failure.Kind == "denied" {
			return Capability{Status: "denied", ReasonCodes: []string{"APP_INSTALLATION_MISSING"}, ObservedAt: &observed}, nil
		}
		return Capability{}, err
	}
	var response struct {
		ID          int64             `json:"id"`
		AppID       int64             `json:"app_id"`
		SuspendedAt json.RawMessage   `json:"suspended_at"`
		Permissions map[string]string `json:"permissions"`
	}
	if err := decode(payload, &response); err != nil {
		return Capability{}, err
	}
	if response.ID <= 0 || strconv.FormatInt(response.AppID, 10) != c.config.AppID || len(response.SuspendedAt) == 0 || response.Permissions == nil {
		return Capability{}, &Error{Kind: "unavailable"}
	}
	result := Capability{Status: "allowed", ReasonCodes: []string{}, ObservedAt: &observed}
	if !bytes.Equal(response.SuspendedAt, []byte("null")) {
		var suspended time.Time
		if json.Unmarshal(response.SuspendedAt, &suspended) != nil || suspended.IsZero() {
			return Capability{}, &Error{Kind: "unavailable"}
		}
		result.Status = "denied"
		result.ReasonCodes = append(result.ReasonCodes, "APP_INSTALLATION_SUSPENDED")
	}
	if response.Permissions["contents"] != "write" || response.Permissions["pull_requests"] != "write" || response.Permissions["metadata"] != "read" {
		result.Status = "denied"
		result.ReasonCodes = append(result.ReasonCodes, "APP_PERMISSION_MISSING")
	}
	return result, nil
}

func parsePrivateKey(data []byte) (*rsa.PrivateKey, error) {
	if len(data) > 64<<10 {
		return nil, &Error{Kind: "unavailable"}
	}
	block, remainder := pem.Decode(data)
	if block == nil || len(bytes.TrimSpace(remainder)) != 0 || len(block.Headers) != 0 {
		return nil, &Error{Kind: "unavailable"}
	}
	var key *rsa.PrivateKey
	switch block.Type {
	case "RSA PRIVATE KEY":
		parsed, err := x509.ParsePKCS1PrivateKey(block.Bytes)
		if err != nil {
			return nil, &Error{Kind: "unavailable"}
		}
		key = parsed
	case "PRIVATE KEY":
		parsed, err := x509.ParsePKCS8PrivateKey(block.Bytes)
		if err != nil {
			return nil, &Error{Kind: "unavailable"}
		}
		var ok bool
		key, ok = parsed.(*rsa.PrivateKey)
		if !ok {
			return nil, &Error{Kind: "unavailable"}
		}
	default:
		return nil, &Error{Kind: "unavailable"}
	}
	if key.N.BitLen() < 2048 || key.Validate() != nil {
		return nil, &Error{Kind: "unavailable"}
	}
	return key, nil
}

func (c *Client) appToken(key *rsa.PrivateKey) (string, error) {
	now := time.Now().UTC()
	claims, err := json.Marshal(struct {
		IssuedAt  int64  `json:"iat"`
		ExpiresAt int64  `json:"exp"`
		Issuer    string `json:"iss"`
	}{IssuedAt: now.Add(-time.Minute).Unix(), ExpiresAt: now.Add(9 * time.Minute).Unix(), Issuer: c.config.ClientID})
	if err != nil {
		return "", &Error{Kind: "unavailable"}
	}
	encoded := base64.RawURLEncoding.EncodeToString([]byte(`{"alg":"RS256","typ":"JWT"}`)) + "." + base64.RawURLEncoding.EncodeToString(claims)
	digest := sha256.Sum256([]byte(encoded))
	signature, err := rsa.SignPKCS1v15(rand.Reader, key, crypto.SHA256, digest[:])
	if err != nil {
		return "", &Error{Kind: "unavailable"}
	}
	return encoded + "." + base64.RawURLEncoding.EncodeToString(signature), nil
}
