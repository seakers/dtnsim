from simulator.reports.DtnAbstractReport import DtnAbstractReport, concat_dfs

class DtnStoredBundlesReport(DtnAbstractReport):

    _alias = 'stored'

    def collect_data(self):
        # Get the bundles stored in all the node's neighbor queues
        df = concat_dfs({nid: concat_dfs({neighbor: node.queues[neighbor].stored
                                          for neighbor in node.neighbors}, 'neighbor')
                                          for nid, node in self.env.nodes.items()}, 'node')

        # Transform to string to save space. You can use a converter when loading
        if 'visited' in df: df.visited = df.visited.apply(lambda v: str(v))

        return df