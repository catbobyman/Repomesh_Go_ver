// Temporary, standard-library-only repair of exactly two c-instance certificates.
// Private keys never leave the container; all other PKI/token files remain unchanged.
package main

import (
 "bytes"
 "crypto"
 "crypto/rand"
 "crypto/sha256"
 "crypto/x509"
 "encoding/json"
 "encoding/pem"
 "fmt"
 "os"
 "path/filepath"
 "reflect"
 "time"
)

const dir = "/data/agentteams-controller/pki"
func must(err error) { if err != nil { panic(err) } }
func read(name string) []byte { b,e:=os.ReadFile(filepath.Join(dir,name));must(e);return b }
func cert(b []byte) *x509.Certificate { p,_:=pem.Decode(b);if p==nil {panic("invalid certificate PEM")};c,e:=x509.ParseCertificate(p.Bytes);must(e);return c }
func summary(c *x509.Certificate) map[string]any { return map[string]any{"subject":c.Subject.String(),"issuer":c.Issuer.String(),"not_before":c.NotBefore,"not_after":c.NotAfter,"serial":c.SerialNumber.String(),"dns_names":c.DNSNames,"ip_addresses":c.IPAddresses,"sha256":fmt.Sprintf("%x",sha256.Sum256(c.Raw)),"public_key_spki_sha256":fmt.Sprintf("%x",sha256.Sum256(c.RawSubjectPublicKeyInfo))} }
func resign(old,parent *x509.Certificate,key crypto.Signer,now time.Time) *x509.Certificate {
 t:=*old;t.NotBefore=now.Add(-time.Minute).Truncate(time.Second);t.ExtraExtensions=old.Extensions
 der,e:=x509.CreateCertificate(rand.Reader,&t,parent,old.PublicKey,key);must(e)
 n,e:=x509.ParseCertificate(der);must(e)
 oldPub,e:=x509.MarshalPKIXPublicKey(old.PublicKey);must(e);newPub,e:=x509.MarshalPKIXPublicKey(n.PublicKey);must(e)
 if !bytes.Equal(oldPub,newPub)||!bytes.Equal(old.RawSubject,n.RawSubject)||!bytes.Equal(old.RawIssuer,n.RawIssuer)||!reflect.DeepEqual(old.Extensions,n.Extensions)||!old.NotAfter.Equal(n.NotAfter)||old.SerialNumber.Cmp(n.SerialNumber)!=0 {panic("certificate identity or extensions changed unexpectedly")}
 return n
}
func main() {
 if os.Getenv("AGENTTEAMS_CONTROLLER_NAME")!="rv-c"||os.Getenv("AGENTTEAMS_DATA_DIR")!="/data/agentteams-controller" {panic("not dedicated c controller")}
 apply:=len(os.Args)==2&&os.Args[1]=="--apply"
 if len(os.Args)>1&&!apply {panic("only --apply allowed")}
 now:=time.Now().UTC();caRaw,leafRaw:=read("ca.crt"),read("apiserver.crt");ca,leaf:=cert(caRaw),cert(leafRaw)
 if ca.Subject.CommonName!="agentteams-ca"||leaf.Subject.CommonName!="kube-apiserver"||!ca.NotBefore.After(now)||!leaf.NotBefore.After(now) {panic("expected only future-dated c certificates")}
 keyBlock,_:=pem.Decode(read("ca.key"));if keyBlock==nil {panic("invalid CA key PEM")}
 parsed,e:=x509.ParseECPrivateKey(keyBlock.Bytes);must(e);var key crypto.Signer=parsed
 pub,e:=x509.MarshalPKIXPublicKey(key.Public());must(e);expected,e:=x509.MarshalPKIXPublicKey(ca.PublicKey);must(e);if !bytes.Equal(pub,expected){panic("CA key mismatch")}
 unchanged:=map[string][32]byte{}
 entries,e:=os.ReadDir(dir);must(e)
 for _,entry:=range entries {if !entry.IsDir()&&entry.Name()!="ca.crt"&&entry.Name()!="apiserver.crt" {unchanged[entry.Name()]=sha256.Sum256(read(entry.Name()))}}
 caNew:=resign(ca,ca,key,now);leafNew:=resign(leaf,caNew,key,now)
 roots:=x509.NewCertPool();roots.AddCert(caNew)
 _,e=leafNew.Verify(x509.VerifyOptions{Roots:roots,CurrentTime:now,DNSName:"localhost"});must(e)
 out:=map[string]any{"mode":"PLAN_CERTIFICATES_NOT_WRITTEN","observed_utc":now,"before":[]any{summary(ca),summary(leaf)},"after":[]any{summary(caNew),summary(leafNew)},"identical_subject_issuer_spki_extensions_serial_not_after":true,"new_chain_verified":true,"keys_exported":false}
 if apply {
  backup:=filepath.Join(filepath.Dir(dir),"pki-clock-recovery-"+now.Format("20060102T150405Z"));must(os.Mkdir(backup,0700))
  must(os.WriteFile(filepath.Join(backup,"ca.crt"),caRaw,0600));must(os.WriteFile(filepath.Join(backup,"apiserver.crt"),leafRaw,0600))
  for name,c:=range map[string]*x509.Certificate{"ca.crt":caNew,"apiserver.crt":leafNew} {target:=filepath.Join(dir,name);tmp:=target+".reissued";must(os.WriteFile(tmp,pem.EncodeToMemory(&pem.Block{Type:"CERTIFICATE",Bytes:c.Raw}),0600));must(os.Rename(tmp,target))}
  for name,hash:=range unchanged {if sha256.Sum256(read(name))!=hash {panic("unexpected change to other PKI file")}}
  out["mode"]="TWO_CERTIFICATES_REISSUED_RESTART_REQUIRED";out["backup_directory"]=backup;out["other_pki_files_unchanged"]=true;out["other_pki_file_count"]=len(unchanged)
 }
 must(json.NewEncoder(os.Stdout).Encode(out))
}
