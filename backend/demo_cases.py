"""Hardcoded demo data: one graph problem, three students, three different causes.
Problem: given a graph (n, m, then m edges), print the number of connected components
and the BFS order from node 0 (for the component containing node 0).
Keep these cached so the demo works even if the LLM API fails.
"""

PROBLEM = """Given an undirected graph with n nodes (0..n-1) and m edges, print the number of
connected components. Input: first line n m, then m lines u v."""

# Dense graph: many converging paths -> visited-on-dequeue pushes far more duplicates.
def _dense_input(n=40):
    edges = [(i, j) for i in range(n) for j in range(i + 1, n)]
    return f"{n} {len(edges)}\n" + "\n".join(f"{u} {v}" for u, v in edges) + "\n"

DEMO_INPUT = _dense_input()

# ---- Student A: state-commit-timing (marks visited on dequeue) ----
STUDENT_A_A = '''
import sys
from collections import deque
pushes = 0
def main():
    global pushes
    data = sys.stdin.read().split()
    n, m = int(data[0]), int(data[1])
    adj = [[] for _ in range(n)]
    for i in range(m):
        u, v = int(data[2+2*i]), int(data[3+2*i])
        adj[u].append(v); adj[v].append(u)
    visited = [False]*n
    comps = 0
    for s in range(n):
        if visited[s]:
            continue
        comps += 1
        q = deque([s]); pushes += 1
        while q:
            u = q.popleft()
            if visited[u]:
                continue
            visited[u] = True          # BUG: committed on dequeue
            for v in adj[u]:
                if not visited[v]:
                    q.append(v); pushes += 1
    print(comps)
main()
print("__METRIC__", pushes)
'''

STUDENT_A_B = '''
import sys
from collections import deque
pushes = 0
def main():
    global pushes
    data = sys.stdin.read().split()
    n, m = int(data[0]), int(data[1])
    adj = [[] for _ in range(n)]
    for i in range(m):
        u, v = int(data[2+2*i]), int(data[3+2*i])
        adj[u].append(v); adj[v].append(u)
    visited = [False]*n
    comps = 0
    for s in range(n):
        if visited[s]:
            continue
        comps += 1
        visited[s] = True              # FIX: commit on enqueue
        q = deque([s]); pushes += 1
        while q:
            u = q.popleft()
            for v in adj[u]:
                if not visited[v]:
                    visited[v] = True  # FIX: commit on enqueue
                    q.append(v); pushes += 1
    print(comps)
main()
print("__METRIC__", pushes)
'''

# ---- Student B: structure-selection (list membership instead of set) ----
# Metric: membership_cost = estimated scan length per membership check (len(list) for a list, 1 for a set).
# A uses a list; B uses a set. Same output, one decision changed (list -> set).
STUDENT_B_A = '''
import sys
from collections import deque
cmp_count = 0
def main():
    global cmp_count
    data = sys.stdin.read().split()
    n, m = int(data[0]), int(data[1])
    adj = [[] for _ in range(n)]
    for i in range(m):
        u, v = int(data[2+2*i]), int(data[3+2*i])
        adj[u].append(v); adj[v].append(u)
    visited = []                       # BUG: list membership is O(n)
    comps = 0
    for s in range(n):
        cmp_count += len(visited)
        if s in visited:
            continue
        comps += 1
        visited.append(s); q = deque([s])
        while q:
            u = q.popleft()
            for v in adj[u]:
                cmp_count += len(visited)
                if v not in visited:
                    visited.append(v); q.append(v)
    print(comps)
main()
print("__METRIC__", cmp_count)
'''

STUDENT_B_B = '''
import sys
from collections import deque
cmp_count = 0
def main():
    global cmp_count
    data = sys.stdin.read().split()
    n, m = int(data[0]), int(data[1])
    adj = [[] for _ in range(n)]
    for i in range(m):
        u, v = int(data[2+2*i]), int(data[3+2*i])
        adj[u].append(v); adj[v].append(u)
    visited = set()                    # FIX: O(1) membership
    comps = 0
    for s in range(n):
        cmp_count += 1
        if s in visited:
            continue
        comps += 1
        visited.add(s); q = deque([s])
        while q:
            u = q.popleft()
            for v in adj[u]:
                cmp_count += 1
                if v not in visited:
                    visited.add(v); q.append(v)
    print(comps)
main()
print("__METRIC__", cmp_count)
'''

# ---- Student C: coverage-completeness (only starts from node 0) ----
# Here outputs DIFFER by design, so C is diagnosed from the failing case (disconnected graph),
# not from an op-count race. Metric: components_found. Use a disconnected input.
DISCONNECTED_INPUT = "6 3\n0 1\n2 3\n4 5\n"   # expected answer: 3

STUDENT_C_A = '''
import sys
from collections import deque
def main():
    data = sys.stdin.read().split()
    n, m = int(data[0]), int(data[1])
    adj = [[] for _ in range(n)]
    for i in range(m):
        u, v = int(data[2+2*i]), int(data[3+2*i])
        adj[u].append(v); adj[v].append(u)
    visited = [False]*n
    comps = 0
    q = deque([0]); visited[0] = True; comps += 1   # BUG: only starts at node 0
    while q:
        u = q.popleft()
        for v in adj[u]:
            if not visited[v]:
                visited[v] = True; q.append(v)
    print(comps)
main()
'''

STUDENT_C_B = STUDENT_A_B  # correct loop over every component

# NOTE: Student C's experiment compares OUTPUTS (A gives 1, B gives 3 on a disconnected graph)
# rather than op counts. run_counterfactual(..., expected_output="3") applies the coverage rule:
# conclusive = (outputs differ AND B matches the expected answer).
DISCONNECTED_EXPECTED = "3"
