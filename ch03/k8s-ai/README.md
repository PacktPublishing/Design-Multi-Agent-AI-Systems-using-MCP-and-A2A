# k8s-ai

Cloned with permission of [the-gigi](https://github.com/the-gigi) from https://github.com/the-gigi/k8s-ai 


OpenAI chatbot with kubectl access. You run it and you interact with your Kubernetes clusters in natural language.

# Setup

## Create virtual environment and activate it

```shell
python -m venv venv
source venv/bin/activate
```

## Install dependencies

```
pip install -r requirements.txt
```

# Usage

Just run the thing and make sure your kube context points to the right cluster:

```shell
python main.py
```

# k8s-ai in Action

Let's create a kind cluster first

```
❯ kind create cluster -n k8s-ai
Creating cluster "k8s-ai" ...
 ✓ Ensuring node image (kindest/node:v1.33.1) 🖼
 ✓ Preparing nodes 📦
 ✓ Writing configuration 📜
 ✓ Starting control-plane 🕹️
 ✓ Installing CNI 🔌
 ✓ Installing StorageClass 💾
Set kubectl context to "kind-k8s-ai"
You can now use your cluster with:

kubectl cluster-info --context kind-k8s-ai

Have a nice day! 👋
```

Now, let's cause some trouble in the cluster. Here is a deployment that will never be ready because it requires its pods
to be scheduled on a node with a label that doesn't exist in the cluster:

```shell
echo '
apiVersion: apps/v1
kind: Deployment
metadata:
  name: some-app
spec:
  replicas: 3
  selector:
    matchLabels:
      app: some-app
  template:
    metadata:
      labels:
        app: some-app
    spec:
      affinity:
        nodeAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
            nodeSelectorTerms:
              - matchExpressions:
                  - key: no-such-node
                    operator: In
                    values:
                      - "true"
      containers:
        - name: pause
          image: registry.k8s.io/pause:3.9
' | kubectl apply -f -
deployment.apps/some-app created
```

Let's confirm that all the pods were created, but none of them are running:

```shell
❯ kubectl get po
NAME                        READY   STATUS    RESTARTS   AGE
some-app-55cb6c5586-25gcj   0/1     Pending   0          117s
some-app-55cb6c5586-6xg2x   0/1     Pending   0          15s
some-app-55cb6c5586-b4sc7   0/1     Pending   0          15s
```

Alright, let's cause more havoc and create a deployment for Nginx with an invalid image name:

```shell
echo '
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx
spec:
  replicas: 1
  selector:
    matchLabels:
      app: nginx
  template:
    metadata:
      labels:
        app: nginx
    spec:
      containers:
        - name: nginx
          image: nnnnnnnnginx
' | kubectl apply -f -

deployment.apps/nginx created
```

Let's check the status of our cluster now:

```shell
❯ kubectl get po
NAME                        READY   STATUS         RESTARTS   AGE
nginx-74f5dd8d8f-zfdmw      0/1     ErrImagePull   0          34s
some-app-55cb6c5586-25gcj   0/1     Pending        0          9m3s
some-app-55cb6c5586-6xg2x   0/1     Pending        0          7m21s
some-app-55cb6c5586-b4sc7   0/1     Pending        0          7m21s
```

So, we have two deployments, one of them has Three pending pods and the other one is in error state. Let's ask k8s-ai to
help us:

```shell
❯ python main.py 
☸️ Interactive Kubernetes Chat. Type 'exit' to quit.
----------------------------------------------------
👤 You: what's the cluster's status?
🤖 AI: The current status of the Kubernetes cluster is as follows:

### Nodes
- **Control Plane Node**: `k8s-ai-control-plane` is in a **Ready** state and running version **v1.33.1**.

### Pods Status
- **Running Pods**:
  - `coredns`: `coredns-674b8bbfcf-rrjdz` and `coredns-674b8bbfcf-w89zr` are both running successfully.
  - `etcd`: Running on `etcd-k8s-ai-control-plane`.
  - Network and Control components like `kindnet`, `kube-apiserver`, `kube-controller-manager`, `kube-proxy`, and `kube-scheduler` are all running.
  - `local-path-provisioner`: Running.

- **Troubled Pods**:
  - In the `default` namespace:
    - `nginx-74f5dd8d8f-zfdmw` has an `ImagePullBackOff` issue.
    - Several `some-app` pods are in a `Pending` state.

### Services
- **ClusterIP Services**:
  - `kubernetes` service is running at IP `10.96.0.1`.
  - KubeDNS service is available at `10.96.0.10` with ports `53/UDP, 53/TCP, 9153/TCP`.

Overall, the cluster's core components and system pods are operational, but there are issues with applications in the 
`default` namespace that need addressing, particularly the `ImagePullBackOff` and `Pending` statuses.
```

OK. That's a pretty good summary. Let's ask it what's the problem with the pending pods:

```
👤 You: find out why the some-app pods are pending
🤖 AI: The `some-app` deployment is configured with a node affinity rule that cannot be satisfied by the current 
cluster node configuration. The specific node affinity configuration is as follows:


affinity:
  nodeAffinity:
    requiredDuringSchedulingIgnoredDuringExecution:
      nodeSelectorTerms:
      - matchExpressions:
        - key: no-such-node
          operator: In
          values:
          - "true"

This configuration is attempting to schedule the pods on nodes that have a label `no-such-node` with the value `"true"`. 
However, the current node, `k8s-ai-control-plane`, does not possess such a label. This results in the pods being unable 
to be scheduled.

### Steps to Correct the Issue:

1. **Modify the Deployment's Node Affinity**:
   - If the affinity rules are not necessary, consider removing or adjusting them from the deployment.
   - If specific node selection criteria are required, ensure that the cluster nodes are labeled accordingly.

2. **Label the Node** (if you intend to keep the affinity rule):
   - Add the required label to the node if the intent is to only run `some-app` pods on a specific subset of nodes. 
   Given the current setup, this would involve adding a label like `no-such-node=true` to `k8s-ai-control-plane`, should 
   this be the intended setup.

Would you like to proceed with modifying the deployment configuration or adding a label to the current node?
----------
```

Nice. Let's ask k8s-ai to add the needed label so the pods can be scheduled:

```shell
👤 You: add the label no-such-node to our control plane node
🤖 AI: The label `no-such-node=true` has been successfully added to the control plane node `k8s-ai-control-plane`.
----------
👤 You: what kubectl commands did you use?
🤖 AI: I used the following `kubectl` commands:
1. `kubectl get nodes` - This command was used to list all the nodes in the Kubernetes cluster to identify the control plane node.
2. `kubectl label nodes k8s-ai-control-plane no-such-node=true` - This command was used to add the label `no-such-node=true` to the control plane node named `k8s-ai-control-plane`.
----------
```

As you can see k8s-ai can execute multiple operations to accomplish a task. In this simple case, it first listed the
nodes,
then it added the label to the control plane node. Let's check the status of the pods now:

```shell
kubectl get po
NAME                        READY   STATUS             RESTARTS   AGE
nginx-74f5dd8d8f-zfdmw      0/1     ImagePullBackOff   0          35m
some-app-65696dbff4-2cph8   1/1     Running            0          2m27s
some-app-65696dbff4-8gbp8   1/1     Running            0          2m28s
some-app-65696dbff4-lxgfb   1/1     Running            0          3m13s
```

Excellent. The pods are running now. Let's see if k8s-ai can fix our nginx deployment:

```shell
👤 You: let's go back to the nginx deployment. suggest options how to fix it
🤖 AI: It looks like there is an issue with the `nginx` deployment due to the incorrect image name. The image name 
`nnnnnnnnginx` seems to be invalid or misspelled for the standard `nginx` image. Here are some options to fix the issue:
1. **Update the Image Name:**
   - Correct the image name in the deployment to a valid `nginx` image, such as `nginx:latest`.
2. **Roll Back the Deployment:**
   - If there was a previous version of the deployment with a valid configuration, you can roll back to that version if the deployment history is available.
3. **Check Image Repository:**
   - Verify whether the image exists in your container registry if you're using a custom image. Make sure it's accessible without authentication issues.
4. **Check Compatibility:**
   - Ensure that the specified image version is compatible with your Kubernetes cluster version.
Would you like me to go ahead with the first option and update the image name in the deployment?
----------
```

Those all sound like good options. Let's go with the first one and update the image name to `nginx:latest`:

```
👤 You: option 1 sounds good. go for it.
🤖 AI: The nginx deployment has been updated with the correct image name and successfully rolled out. If you have any more questions or need further assistance, feel free to ask!
----------
```

Alright. Now, that we trust k8s-ai we don't need to run `kubectl get pods` commands ourselves we can just ask k8s-ai to
do it for us.

```
👤 You: show me the pods
🤖 AI: The pods are up and running successfully:
- **nginx-5869d7778c-wjcsz**: Running
- **some-app-65696dbff4-2cph8**: Running
- **some-app-65696dbff4-8gbp8**: Running
- **some-app-65696dbff4-lxgfb**: Running
The nginx deployment is now fixed and operational. If you need further assistance, feel free to ask!
```
