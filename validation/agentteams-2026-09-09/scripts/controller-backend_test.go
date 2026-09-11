package backend

import("encoding/json";"testing")

func TestValidationDockerResourcesAbsentFromPayload(t *testing.T){
 d:=&DockerBackend{}
 req:=CreateRequest{Name:"validation",Image:"validation:local",Network:"validation-net",Resources:&ResourceRequirements{CPURequest:"250m",CPULimit:"1",MemoryRequest:"256Mi",MemoryLimit:"512Mi"}}
 p:=d.buildCreatePayload(req,"",0);b,err:=json.Marshal(p);if err!=nil{t.Fatal(err)};t.Logf("requested limits cpu=1 memory=512Mi actual payload=%s",b)
 var obj map[string]any;_ =json.Unmarshal(b,&obj);hc,ok:=obj["HostConfig"].(map[string]any);if !ok{t.Fatal("HostConfig missing despite Network")}
 for _,field:=range []string{"Memory","MemoryReservation","NanoCpus","CpuQuota","CpuPeriod","CpuShares","PidsLimit"}{if _,exists:=hc[field];exists{t.Fatalf("unexpected resource projection: %s",field)}}
}
