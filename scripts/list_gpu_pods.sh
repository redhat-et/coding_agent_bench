#!/bin/sh
oc get pods --all-namespaces -o json | python3 -c '
import json,sys
data=json.load(sys.stdin)
for p in data["items"]:
    for c in p["spec"].get("containers",[]):
        gpu=c.get("resources",{}).get("requests",{}).get("nvidia.com/gpu","0")
        if gpu!="0":
            ns=p["metadata"]["namespace"]
            name=p["metadata"]["name"]
            node=p["spec"].get("nodeName","unscheduled")
            print(ns+"/"+name+" - "+gpu+" GPU(s) - Node: "+node)
'
