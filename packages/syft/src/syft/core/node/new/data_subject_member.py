# relative
from ....core.node.common.node_table.syft_object import SYFT_OBJECT_VERSION_1
from ....core.node.common.node_table.syft_object import SyftObject
from ...common.serde.serializable import serializable
from .document_store import PartitionKey

ParentPartitionKey = PartitionKey(key="parent", type_=str)
ChildPartitionKey = PartitionKey(key="child", type_=str)


@serializable(recursive_serde=True)
class DataSubjectMemberRelationship(SyftObject):
    __canonical_name__ = "DataSubjectMemberRelationship"
    __version__ = SYFT_OBJECT_VERSION_1

    parent: str
    child: str

    __attr_searchable__ = ["parent", "child"]
    __attr_unique__ = ["parent", "child"]

    def __hash__(self) -> int:
        return hash(self.parent + self.child)

    def __eq__(self, other) -> bool:
        return hash(self) == hash(other)

    def __repr__(self) -> str:
        return f"<DataSubjectMembership: {self.parent} -> {self.child}>"
