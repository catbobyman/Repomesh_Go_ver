//go:build !unix

package secrets

func readRootFile(string) ([]byte, error) {
	return nil, ErrConfiguration
}
