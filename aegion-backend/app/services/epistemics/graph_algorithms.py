"""
Aegion Knowledge Graph Algorithms.

Phase 5: Advanced Graph Algorithms.
PageRank, Community Detection, Centrality Measures, and Influence Analysis.
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
import math

from ..ports.knowledge_graph import GraphNode, GraphNodeType


class CentralityType(str, Enum):
    """Types of centrality measures."""
    DEGREE = "degree"
    BETWEENNESS = "betweenness"
    CLOSENESS = "closeness"
    PAGERANK = "pagerank"
    EIGENVECTOR = "eigenvector"


@dataclass
class PageRankResult:
    """PageRank result for a node."""
    node_id: str
    score: float
    rank: int
    percentile: float


@dataclass
class CommunityResult:
    """Community detection result."""
    community_id: int
    member_node_ids: List[str]
    size: int
    density: float
    central_node_id: Optional[str] = None


@dataclass
class CentralityResult:
    """Centrality measure result."""
    node_id: str
    centrality_type: CentralityType
    score: float
    normalized_score: float
    rank: int


@dataclass
class InfluenceAnalysis:
    """Influence analysis for a node."""
    node_id: str
    direct_influence: int  # Outgoing edges
    indirect_influence: int  # Reachable nodes
    influence_depth: int  # Max path length
    influenced_communities: List[int]
    influence_score: float  # Composite score


@dataclass
class GraphAlgorithmReport:
    """Complete graph algorithm analysis report."""
    workspace_id: str
    generated_at: datetime
    node_count: int
    edge_count: int
    pagerank_results: List[PageRankResult]
    communities: List[CommunityResult]
    centrality_results: Dict[CentralityType, List[CentralityResult]]
    key_insights: List[str]


class GraphAlgorithms:
    """
    Advanced graph algorithms for knowledge graph analysis.
    
    Doctrine: "Structure reveals meaning."
    
    Works with both in-memory graphs and Neo4j.
    """
    
    def __init__(
        self,
        damping_factor: float = 0.85,  # PageRank damping
        max_iterations: int = 100,      # PageRank iterations
        convergence_threshold: float = 0.0001
    ):
        self.damping_factor = damping_factor
        self.max_iterations = max_iterations
        self.convergence_threshold = convergence_threshold
    
    # ========== PageRank ==========
    
    def compute_pagerank(
        self,
        nodes: List[str],
        edges: List[Tuple[str, str]],  # (source, target)
        initial_scores: Optional[Dict[str, float]] = None
    ) -> List[PageRankResult]:
        """
        Compute PageRank scores for all nodes.
        
        Uses iterative power method.
        """
        if not nodes:
            return []
        
        n = len(nodes)
        node_index = {node: i for i, node in enumerate(nodes)}
        
        # Build adjacency list
        outgoing: Dict[str, List[str]] = {node: [] for node in nodes}
        for source, target in edges:
            if source in outgoing:
                outgoing[source].append(target)
        
        # Initialize scores
        if initial_scores:
            scores = {node: initial_scores.get(node, 1.0 / n) for node in nodes}
        else:
            scores = {node: 1.0 / n for node in nodes}
        
        # Iterate
        for iteration in range(self.max_iterations):
            new_scores = {}
            max_diff = 0.0
            
            for node in nodes:
                # Calculate incoming contributions
                incoming_sum = 0.0
                for source, targets in outgoing.items():
                    if node in targets:
                        out_degree = len(outgoing[source])
                        if out_degree > 0:
                            incoming_sum += scores[source] / out_degree
                
                # Apply damping
                new_score = (1 - self.damping_factor) / n + self.damping_factor * incoming_sum
                new_scores[node] = new_score
                max_diff = max(max_diff, abs(new_score - scores[node]))
            
            scores = new_scores
            
            if max_diff < self.convergence_threshold:
                break
        
        # Sort and rank
        sorted_nodes = sorted(nodes, key=lambda x: scores[x], reverse=True)
        
        results = []
        for rank, node in enumerate(sorted_nodes, 1):
            results.append(PageRankResult(
                node_id=node,
                score=scores[node],
                rank=rank,
                percentile=100 * (n - rank + 1) / n
            ))
        
        return results
    
    # ========== Community Detection ==========
    
    def detect_communities_louvain(
        self,
        nodes: List[str],
        edges: List[Tuple[str, str, float]]  # (source, target, weight)
    ) -> List[CommunityResult]:
        """
        Detect communities using simplified Louvain algorithm.
        
        Uses modularity optimization.
        """
        if not nodes or not edges:
            return []
        
        # Build adjacency with weights
        adjacency: Dict[str, Dict[str, float]] = {node: {} for node in nodes}
        total_weight = 0.0
        
        for source, target, weight in edges:
            if source in adjacency and target in adjacency:
                adjacency[source][target] = weight
                adjacency[target][source] = weight
                total_weight += weight
        
        # Initial community assignment (each node is its own community)
        community: Dict[str, int] = {node: i for i, node in enumerate(nodes)}
        
        # Iterate until no improvement
        improved = True
        while improved:
            improved = False
            
            for node in nodes:
                current_community = community[node]
                best_community = current_community
                best_gain = 0.0
                
                # Find neighboring communities
                neighbor_communities = set()
                for neighbor in adjacency[node]:
                    neighbor_communities.add(community[neighbor])
                
                # Try moving to each neighboring community
                for target_community in neighbor_communities:
                    if target_community == current_community:
                        continue
                    
                    gain = self._modularity_gain(
                        node, current_community, target_community,
                        community, adjacency, total_weight
                    )
                    
                    if gain > best_gain:
                        best_gain = gain
                        best_community = target_community
                
                if best_community != current_community and best_gain > 0:
                    community[node] = best_community
                    improved = True
        
        # Group results
        communities_map: Dict[int, List[str]] = {}
        for node, comm_id in community.items():
            if comm_id not in communities_map:
                communities_map[comm_id] = []
            communities_map[comm_id].append(node)
        
        results = []
        for comm_id, members in communities_map.items():
            # Calculate density
            internal_edges = sum(
                1 for source, target, _ in edges
                if source in members and target in members
            )
            max_edges = len(members) * (len(members) - 1) / 2
            density = internal_edges / max_edges if max_edges > 0 else 0
            
            # Find central node (highest degree within community)
            central_node = max(
                members,
                key=lambda n: sum(1 for neighbor in adjacency[n] if neighbor in members)
            )
            
            results.append(CommunityResult(
                community_id=comm_id,
                member_node_ids=members,
                size=len(members),
                density=density,
                central_node_id=central_node
            ))
        
        return sorted(results, key=lambda c: c.size, reverse=True)
    
    def _modularity_gain(
        self,
        node: str,
        from_community: int,
        to_community: int,
        community: Dict[str, int],
        adjacency: Dict[str, Dict[str, float]],
        total_weight: float
    ) -> float:
        """Calculate modularity gain from moving node."""
        if total_weight == 0:
            return 0.0
        
        # Weight of edges from node to target community
        to_weight = sum(
            adjacency[node].get(neighbor, 0)
            for neighbor in adjacency
            if community[neighbor] == to_community
        )
        
        # Weight of edges from node to current community
        from_weight = sum(
            adjacency[node].get(neighbor, 0)
            for neighbor in adjacency
            if community[neighbor] == from_community and neighbor != node
        )
        
        # Degree of node
        node_degree = sum(adjacency[node].values())
        
        # Sum of degrees in communities
        to_degree = sum(
            sum(adjacency[n].values())
            for n in adjacency
            if community[n] == to_community
        )
        from_degree = sum(
            sum(adjacency[n].values())
            for n in adjacency
            if community[n] == from_community
        ) - node_degree
        
        # Modularity delta
        gain = (to_weight - from_weight) / total_weight
        gain -= self.damping_factor * node_degree * (to_degree - from_degree) / (2 * total_weight * total_weight)
        
        return gain
    
    # ========== Centrality Measures ==========
    
    def compute_degree_centrality(
        self,
        nodes: List[str],
        edges: List[Tuple[str, str]]
    ) -> List[CentralityResult]:
        """Compute degree centrality."""
        degree: Dict[str, int] = {node: 0 for node in nodes}
        
        for source, target in edges:
            if source in degree:
                degree[source] += 1
            if target in degree:
                degree[target] += 1
        
        max_degree = max(degree.values()) if degree else 1
        
        sorted_nodes = sorted(nodes, key=lambda n: degree[n], reverse=True)
        
        return [
            CentralityResult(
                node_id=node,
                centrality_type=CentralityType.DEGREE,
                score=float(degree[node]),
                normalized_score=degree[node] / max_degree if max_degree > 0 else 0,
                rank=rank
            )
            for rank, node in enumerate(sorted_nodes, 1)
        ]
    
    def compute_betweenness_centrality(
        self,
        nodes: List[str],
        edges: List[Tuple[str, str]]
    ) -> List[CentralityResult]:
        """
        Compute betweenness centrality.
        
        Uses Brandes' algorithm for efficiency.
        """
        # Build adjacency
        adjacency: Dict[str, List[str]] = {node: [] for node in nodes}
        for source, target in edges:
            if source in adjacency:
                adjacency[source].append(target)
            if target in adjacency:
                adjacency[target].append(source)
        
        centrality: Dict[str, float] = {node: 0.0 for node in nodes}
        
        for source in nodes:
            # BFS from source
            stack = []
            predecessors: Dict[str, List[str]] = {node: [] for node in nodes}
            sigma: Dict[str, int] = {node: 0 for node in nodes}
            sigma[source] = 1
            distance: Dict[str, int] = {node: -1 for node in nodes}
            distance[source] = 0
            
            queue = [source]
            while queue:
                v = queue.pop(0)
                stack.append(v)
                
                for w in adjacency[v]:
                    if distance[w] < 0:
                        distance[w] = distance[v] + 1
                        queue.append(w)
                    if distance[w] == distance[v] + 1:
                        sigma[w] += sigma[v]
                        predecessors[w].append(v)
            
            # Backpropagate
            delta: Dict[str, float] = {node: 0.0 for node in nodes}
            while stack:
                w = stack.pop()
                for v in predecessors[w]:
                    delta[v] += (sigma[v] / sigma[w]) * (1 + delta[w])
                if w != source:
                    centrality[w] += delta[w]
        
        # Normalize
        n = len(nodes)
        if n > 2:
            scale = 1.0 / ((n - 1) * (n - 2))
            for node in centrality:
                centrality[node] *= scale
        
        max_centrality = max(centrality.values()) if centrality else 1
        sorted_nodes = sorted(nodes, key=lambda n: centrality[n], reverse=True)
        
        return [
            CentralityResult(
                node_id=node,
                centrality_type=CentralityType.BETWEENNESS,
                score=centrality[node],
                normalized_score=centrality[node] / max_centrality if max_centrality > 0 else 0,
                rank=rank
            )
            for rank, node in enumerate(sorted_nodes, 1)
        ]
    
    def compute_closeness_centrality(
        self,
        nodes: List[str],
        edges: List[Tuple[str, str]]
    ) -> List[CentralityResult]:
        """Compute closeness centrality."""
        # Build adjacency
        adjacency: Dict[str, List[str]] = {node: [] for node in nodes}
        for source, target in edges:
            if source in adjacency:
                adjacency[source].append(target)
            if target in adjacency:
                adjacency[target].append(source)
        
        centrality: Dict[str, float] = {}
        
        for node in nodes:
            # BFS to find distances
            distances: Dict[str, int] = {node: 0}
            queue = [node]
            
            while queue:
                current = queue.pop(0)
                for neighbor in adjacency[current]:
                    if neighbor not in distances:
                        distances[neighbor] = distances[current] + 1
                        queue.append(neighbor)
            
            # Calculate closeness
            total_distance = sum(distances.values())
            reachable = len(distances) - 1
            
            if reachable > 0 and total_distance > 0:
                centrality[node] = reachable / total_distance
            else:
                centrality[node] = 0.0
        
        max_centrality = max(centrality.values()) if centrality else 1
        sorted_nodes = sorted(nodes, key=lambda n: centrality[n], reverse=True)
        
        return [
            CentralityResult(
                node_id=node,
                centrality_type=CentralityType.CLOSENESS,
                score=centrality[node],
                normalized_score=centrality[node] / max_centrality if max_centrality > 0 else 0,
                rank=rank
            )
            for rank, node in enumerate(sorted_nodes, 1)
        ]
    
    # ========== Influence Analysis ==========
    
    def analyze_influence(
        self,
        node_id: str,
        nodes: List[str],
        edges: List[Tuple[str, str]],
        communities: Optional[List[CommunityResult]] = None
    ) -> InfluenceAnalysis:
        """Analyze a node's influence in the graph."""
        # Build adjacency
        outgoing: Dict[str, List[str]] = {node: [] for node in nodes}
        for source, target in edges:
            if source in outgoing:
                outgoing[source].append(target)
        
        # Direct influence (outgoing edges)
        direct_influence = len(outgoing.get(node_id, []))
        
        # Indirect influence (reachable nodes via BFS)
        visited = set()
        queue = [(node_id, 0)]
        max_depth = 0
        
        while queue:
            current, depth = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            max_depth = max(max_depth, depth)
            
            for neighbor in outgoing.get(current, []):
                if neighbor not in visited:
                    queue.append((neighbor, depth + 1))
        
        indirect_influence = len(visited) - 1  # Exclude self
        
        # Find influenced communities
        influenced_communities = []
        if communities:
            for comm in communities:
                if any(member in visited for member in comm.member_node_ids):
                    influenced_communities.append(comm.community_id)
        
        # Composite score
        influence_score = (
            direct_influence * 0.3 +
            indirect_influence * 0.4 +
            max_depth * 0.2 +
            len(influenced_communities) * 0.1
        )
        
        return InfluenceAnalysis(
            node_id=node_id,
            direct_influence=direct_influence,
            indirect_influence=indirect_influence,
            influence_depth=max_depth,
            influenced_communities=influenced_communities,
            influence_score=influence_score
        )
    
    # ========== Full Analysis ==========
    
    def analyze_graph(
        self,
        workspace_id: str,
        nodes: List[str],
        edges: List[Tuple[str, str, float]]  # (source, target, weight)
    ) -> GraphAlgorithmReport:
        """Run comprehensive graph analysis."""
        simple_edges = [(s, t) for s, t, _ in edges]
        
        # Run algorithms
        pagerank = self.compute_pagerank(nodes, simple_edges)
        communities = self.detect_communities_louvain(nodes, edges)
        
        degree = self.compute_degree_centrality(nodes, simple_edges)
        betweenness = self.compute_betweenness_centrality(nodes, simple_edges)
        closeness = self.compute_closeness_centrality(nodes, simple_edges)
        
        # Generate insights
        insights = []
        
        if pagerank:
            top_node = pagerank[0].node_id
            insights.append(f"Most influential node: {top_node} (PageRank: {pagerank[0].score:.4f})")
        
        if communities:
            insights.append(f"Detected {len(communities)} communities")
            largest = communities[0]
            insights.append(f"Largest community has {largest.size} nodes (density: {largest.density:.2f})")
        
        if betweenness:
            bridge_node = betweenness[0].node_id
            insights.append(f"Key bridge node: {bridge_node}")
        
        return GraphAlgorithmReport(
            workspace_id=workspace_id,
            generated_at=datetime.now(timezone.utc),
            node_count=len(nodes),
            edge_count=len(edges),
            pagerank_results=pagerank[:20],  # Top 20
            communities=communities,
            centrality_results={
                CentralityType.DEGREE: degree[:20],
                CentralityType.BETWEENNESS: betweenness[:20],
                CentralityType.CLOSENESS: closeness[:20],
            },
            key_insights=insights
        )


# Singleton accessor
_algorithms: Optional[GraphAlgorithms] = None

def get_graph_algorithms() -> GraphAlgorithms:
    """Get singleton graph algorithms instance."""
    global _algorithms
    if _algorithms is None:
        _algorithms = GraphAlgorithms()
    return _algorithms
