package server

// Validation probes run the pinned upstream implementation with in-memory
// storage/Kubernetes and backend doubles; they are not deployment acceptance.
import (
 "context"
 "encoding/json"
 "errors"
 "net/http"
 "net/http/httptest"
 "strings"
 "testing"

 v1beta1 "github.com/agentscope-ai/AgentTeams/agentteams-controller/api/v1beta1"
 authpkg "github.com/agentscope-ai/AgentTeams/agentteams-controller/internal/auth"
 "github.com/agentscope-ai/AgentTeams/agentteams-controller/internal/backend"
 "github.com/agentscope-ai/AgentTeams/agentteams-controller/internal/oss/ossfake"
 metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
 "sigs.k8s.io/controller-runtime/pkg/client"
 "sigs.k8s.io/controller-runtime/pkg/client/fake"
)

func TestValidationPauseThenReplan(t *testing.T) {
 store := ossfake.NewMemory()
 key := "shared/projects/p1/meta.json"
 putProject(store,key,map[string]any{"project_id":"p1","status":"active","plan_type":"dag"})
 h := newProjectTestHandler(t,store)
 invoke := func(name,body string,fn http.HandlerFunc,want int) {
  r:=httptest.NewRequest("POST","/api/v1/projects/p1/"+name,strings.NewReader(body)); r.SetPathValue("id","p1")
  r=withCaller(r,&authpkg.CallerIdentity{Role:authpkg.RoleAdmin,Username:"validation"})
  w:=httptest.NewRecorder(); fn(w,r); t.Logf("%s status=%d body=%s",name,w.Code,w.Body.String())
  if w.Code!=want {t.Fatalf("want %d",want)}
 }
 invoke("pause",`{"reason":"review"}`,h.PauseProject,200)
 invoke("replan",`{"tasks":[{"taskId":"new-t1","title":"next"}]}`,h.ReplanProject,409)
 invoke("resume",`{}`,h.ResumeProject,200)
 invoke("replan",`{"tasks":[{"taskId":"new-t1","title":"next"}]}`,h.ReplanProject,200)
 b,_:=store.GetObject(context.Background(),key); t.Logf("persisted=%s",b)
}

func TestValidationReplanStatusMatrix(t *testing.T) {
 for _,c:=range []struct{status,plan,task string; want int}{
  {"active","dag","planned",200},{"active","","planned",200},
  {"paused","dag","planned",409},{"completed","dag","completed",409},
  {"active","loop","planned",409},{"active","dag","in_progress",409},
  {"active","dag","submitted",409},{"active","dag","completed",200},
 } {t.Run(c.status+"_"+c.plan+"_"+c.task,func(t *testing.T){
  store:=ossfake.NewMemory();putProject(store,"shared/projects/p1/meta.json",map[string]any{"project_id":"p1","status":c.status,"plan_type":c.plan,"tasks":[]map[string]any{{"task_id":"old","status":c.task}}})
  h:=newProjectTestHandler(t,store);r:=httptest.NewRequest("POST","/api/v1/projects/p1/replan",strings.NewReader(`{"tasks":[{"taskId":"next"}]}`));r.SetPathValue("id","p1");r=withCaller(r,&authpkg.CallerIdentity{Role:authpkg.RoleAdmin,Username:"validation"})
  w:=httptest.NewRecorder();h.ReplanProject(w,r);t.Logf("status=%d body=%s",w.Code,w.Body.String());if w.Code!=c.want{t.Fatalf("want %d",c.want)}
 })}
}

func TestValidationCreateWorkerRemoteSkillsReadback(t *testing.T) {
 k:=fake.NewClientBuilder().WithScheme(newServerTestScheme(t)).Build();h:=NewResourceHandler(k,"default",nil,"")
 body:=`{"name":"validation-worker","runtime":"qwenpaw","model":"validation-model","remoteSkills":[{"source":"https://example.invalid/skills","skills":[{"name":"validation-skill"}]}],"resources":{"limits":{"cpu":"1","memory":"512Mi"}}}`
 r:=httptest.NewRequest("POST","/api/v1/workers",strings.NewReader(body));w:=httptest.NewRecorder();h.CreateWorker(w,r)
 if w.Code!=201{t.Fatalf("create=%d %s",w.Code,w.Body.String())}
 var worker v1beta1.Worker;if err:=k.Get(context.Background(),client.ObjectKey{Name:"validation-worker",Namespace:"default"},&worker);err!=nil{t.Fatal(err)}
 t.Logf("create=201 remoteSkills stored=%d model=%s runtime=%s limits=%+v",len(worker.Spec.RemoteSkills),worker.Spec.Model,worker.Spec.Runtime,worker.Spec.Resources)
 if len(worker.Spec.RemoteSkills)!=0{t.Fatal("upstream behavior changed: remoteSkills was preserved")}
 if worker.Spec.Resources==nil||worker.Spec.Resources.Limits.CPU!="1"{t.Fatal("resource readback failed")}
}

type validationFailedStart struct{stubWorkerBackend}
func(s *validationFailedStart)Start(context.Context,string)error{s.startCalls++;return errors.New("injected backend start failure")}

func TestValidationReadyRestartAndLateReport(t *testing.T){
 worker:=&v1beta1.Worker{ObjectMeta:metav1.ObjectMeta{Name:"w",Namespace:"default"},Status:v1beta1.WorkerStatus{Phase:"Running"}}
 k:=fake.NewClientBuilder().WithScheme(newLifecycleTestScheme(t)).WithStatusSubresource(&v1beta1.Worker{}).WithObjects(worker).Build()
 reg:=backend.NewRegistry([]backend.WorkerBackend{&stubWorkerBackend{status:backend.StatusRunning}})
 h:=NewLifecycleHandler(k,reg,"default")
 call:=func(fn http.HandlerFunc) *httptest.ResponseRecorder {r:=httptest.NewRequest("POST","/api/v1/workers/w/ready",strings.NewReader(`{"attempt":"old-attempt"}`));r.SetPathValue("name","w");w:=httptest.NewRecorder();fn(w,r);return w}
 phase:=func(h *LifecycleHandler)string{w:=call(h.EnsureReady);var p WorkerLifecycleResponse;if err:=json.Unmarshal(w.Body.Bytes(),&p);err!=nil{t.Fatal(err)};return p.Phase}
 call(h.Ready); if phase(h)!="Ready"{t.Fatal("ready not accepted")};t.Log("before handler restart: Ready")
 h=NewLifecycleHandler(k,reg,"default");if phase(h)!="Running"{t.Fatal("ready unexpectedly durable")};t.Log("new handler, same persisted worker: Running")
 call(h.Ready);if phase(h)!="Ready"{t.Fatal("late report rejected")};t.Log("late report body attempt=old-attempt accepted: Ready; auth middleware not exercised")
}

func TestValidationEnsureReadyStartFailure(t *testing.T){
 worker:=&v1beta1.Worker{ObjectMeta:metav1.ObjectMeta{Name:"w",Namespace:"default"},Status:v1beta1.WorkerStatus{Phase:"Sleeping"}}
 k:=fake.NewClientBuilder().WithScheme(newLifecycleTestScheme(t)).WithStatusSubresource(&v1beta1.Worker{}).WithObjects(worker).Build()
 b:=&validationFailedStart{};h:=NewLifecycleHandler(k,backend.NewRegistry([]backend.WorkerBackend{b}),"default")
 r:=httptest.NewRequest("POST","/api/v1/workers/w/ensure-ready",nil);r.SetPathValue("name","w");w:=httptest.NewRecorder();h.EnsureReady(w,r)
 t.Logf("startCalls=%d response=%d %s",b.startCalls,w.Code,w.Body.String())
 var resp WorkerLifecycleResponse;_ = json.Unmarshal(w.Body.Bytes(),&resp)
 if b.startCalls!=1||w.Code!=200||resp.Phase!="Running"{t.Fatal("unexpected behavior")}
}

func TestValidationWorkflowStatusLosesDistinctions(t *testing.T){
 for _,c:=range []struct{raw,want string}{{"in_progress","in-progress"},{"submitted","in-progress"},{"blocked","blocked"},{"cancelled","blocked"}}{
  got:=normalizeTaskStatus(c.raw);t.Logf("raw=%s normalized=%s",c.raw,got);if got!=c.want{t.Fatalf("want %s",c.want)}
 }
}
