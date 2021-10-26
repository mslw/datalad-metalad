"""
Search through MTreeNode based trees.

This implementation tries to keep memory usage low by:
 - using generators
 - purging MTreeNode-objects, what is not needed anymore

"""
import enum
import fnmatch
from collections import deque
from dataclasses import dataclass
from typing import (
    Generator,
    Optional,
    Union,
)

from dataladmetadatamodel.mappableobject import MappableObject
from dataladmetadatamodel.metadatapath import MetadataPath
from dataladmetadatamodel.mtreenode import MTreeNode


root_path = MetadataPath("")


@dataclass(frozen=True)
class StackItem:
    item_path: MetadataPath
    item_level: int
    node: Union[MTreeNode, MappableObject]
    needs_purge: bool


class TraversalOrder(enum.Enum):
    depth_first_search = 0
    breadth_first_search = 1


class MatchType(enum.Enum):
    full_match = 0
    item_match = 1


class MTreeSearch:
    def __init__(self,
                 mtree: MTreeNode):
        self.mtree = mtree

    def search_pattern(self,
                       pattern: MetadataPath,
                       traversal_order: TraversalOrder = TraversalOrder.depth_first_search,
                       item_indicator: Optional[str] = None,
                       ) -> Generator:
        """
        Search the tree und yield nodes that match the pattern.

        Parameters
        ----------
        pattern: file name with shell-style wildcards
        traversal_order: specify whether to use depth-first-order
                         or breadth-first-order in search
        item_indicator: a string that indicates that the current
                        mtree-node is an item in an enclosing context,
                        for example: ".datalad_metadata-root-record"
                        could indicate a dataset-node.

        Returns
        -------
        Yields a 3-tuple, which describes a full-match, or an item-match.
        A full-match is a tree-node
        whose path matches the complete pattern. An item-match is a
        tree-node that is an item-node and which is matched by a prefix
        of the pattern. Item-matches are only generated, when item_indicator
        is not None.

        In a full-match the first element is the MetadataPath of the matched
        node, the second element is the matched node, and the third
        element is always None.

        In an item match, the first element is the MetadataPath of the
        item-node, the second element is the item node, and the third
        element is a MetadataPath containing the remaining pattern.
        """

        pattern_elements = pattern.parts

        to_process = deque([
            StackItem(
                MetadataPath(""),
                0,
                self.mtree,
                self.mtree.ensure_mapped())])

        while to_process:
            if traversal_order == TraversalOrder.depth_first_search:
                current_item = to_process.pop()
            else:
                current_item = to_process.popleft()

            # If the current item level is equal to the number of
            # pattern elements, i.e. all pattern element were matched
            # earlier, the current item is a valid match.
            if len(pattern_elements) == current_item.item_level:
                yield current_item.item_path, current_item.node, None

                # There will be no further matches below the
                # current item, because the pattern elements are
                # exhausted. Go to the next item.
                continue

            # Check for item-node, if item indicator is not None
            if item_indicator is not None:
                if isinstance(current_item.node, MTreeNode):
                    if item_indicator in current_item.node.child_nodes:
                        yield current_item.item_path, current_item.node, MetadataPath(
                                *pattern_elements[current_item.item_level:])

            # There is at least one more pattern element, try to
            # match it against the current nodes children.
            if not isinstance(current_item.node, MTreeNode):
                # If the current node has no children, we cannot
                # match anything and go to the next item
                continue

            # Check whether the current pattern matches any children,
            # if it does, add the children to `to_process`.
            for child_name in current_item.node.child_nodes:
                if fnmatch.fnmatch(child_name, pattern_elements[current_item.item_level]):
                    child_mtree = current_item.node.get_child(child_name)
                    to_process.append(
                        StackItem(
                            current_item.item_path / child_name,
                            current_item.item_level + 1,
                            child_mtree,
                            child_mtree.ensure_mapped()
                        )
                    )

            # We are done with this node. Purge it, if it was
            # not present in memory before this search.
            if current_item.needs_purge:
                current_item.node.purge()
