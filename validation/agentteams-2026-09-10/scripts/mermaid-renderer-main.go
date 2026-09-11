package main

import (
 "encoding/json"
 "os"
 w "github.com/agentscope-ai/AgentTeams/agentteams-controller/internal/workflow"
)

type specimen struct {
 Name string `json:"name"`
 Snapshot w.Snapshot `json:"snapshot"`
 Mermaid string `json:"mermaid"`
}

func main() {
 cases := []specimen{
  {Name:"baseline", Snapshot:w.Snapshot{Nodes:[]w.Node{{ID:"t1",Name:"Task 1",Status:"completed"},{ID:"t2",Name:"Task 2",Status:"delegated"}},Edges:[]w.Edge{{Source:"t1",Target:"t2"}},Next:[]string{"t2"}}},
  {Name:"empty", Snapshot:w.Snapshot{}},
  {Name:"id_collision",Snapshot:w.Snapshot{Nodes:[]w.Node{{ID:"a.b",Name:"First"},{ID:"a_b",Name:"Second"}},Edges:[]w.Edge{{Source:"a.b",Target:"a_b"}}}},
 }
 titles:=[]string{"say \"hello\" & 'world'", "line1\nline2", "ends with backslash\\", "A --> B", "task [3] (final) ] [", "tab\there\x00nul", "任务一：设计评审", "x --> y\nz[\"quoted\"]"}
 for i,title:=range titles {cases=append(cases,specimen{Name:"title_"+string(rune('1'+i)),Snapshot:w.Snapshot{Nodes:[]w.Node{{ID:"t1",Name:title,Status:"pending"}}}})}
 for _,id:=range []string{"end","subgraph","direction","classDef","graph","1","-"} {cases=append(cases,specimen{Name:"id_"+id,Snapshot:w.Snapshot{Nodes:[]w.Node{{ID:id,Name:"ordinary title",Status:"pending"}}}})}
 for i:=range cases {cases[i].Mermaid=w.RenderMermaid(&cases[i].Snapshot)}
 if err:=json.NewEncoder(os.Stdout).Encode(cases);err!=nil {panic(err)}
}
