# third party
from result import Err
from result import Ok
from result import Result

# relative
from ....core.node.common.node_table.syft_object import SyftObject
from ...common.serde.serializable import serializable
from ...common.uid import UID
from .context import AuthedServiceContext
from .context import UnauthedServiceContext
from .credentials import UserLoginCredentials
from .service import AbstractService
from .service import service_method
from .user import User
from .user import UserPrivateKey
from .user import UserUpdate
from .user import check_pwd
from .user_stash import UserStash

# class UserQuery:
#     email: str
#     name: str
#     verify_key: SyftVerifyKey


@serializable(recursive_serde=True)
class UserService(AbstractService):
    def __init__(self, stash: UserStash) -> None:
        self.stash = stash
        self.collection_keys = {}

    @service_method(path="user.create", name="create")
    def create(
        self, context: AuthedServiceContext, user_update: UserUpdate
    ) -> Result[UserUpdate, str]:
        """TEST MY DOCS"""
        if user_update.id is None:
            user_update.id = UID()
        user = user_update.to(User)

        result = self.set(context=context, syft_object=user)
        if result.is_ok():
            return Ok(user.to(UserUpdate))
        else:
            return Err("Failed to create User.")

    @service_method(path="user.view", name="view")
    def view(self, context: AuthedServiceContext, uid: UID) -> Result[UserUpdate, str]:
        user_result = self.get(context=context, uid=uid)
        if user_result.is_ok():
            return Ok(user_result.ok().to(UserUpdate))
        else:
            return Err(f"Failed to get User for UID: {uid}")

    def set(
        self, context: AuthedServiceContext, syft_object: SyftObject
    ) -> Result[bool, str]:
        self.stash.set(syft_object)
        return Ok(True)

    def exchange_credentials(
        self, context: UnauthedServiceContext
    ) -> Result[UserLoginCredentials, str]:
        """Verify user
        TODO: We might want to use a SyftObject instead
        """
        # for _, user in self.data.items():
        # syft_object: User = SyftObject.from_mongo(user)
        # 🟡 TOD 234: Store real root user and fetch from collectionO🟡
        syft_object = context.node.root_user
        if (syft_object.email == context.login_credentials.email) and check_pwd(
            context.login_credentials.password,
            syft_object.hashed_password,
        ):
            return Ok(syft_object.to(UserPrivateKey))

        return Err(
            f"No user exists with {context.login_credentials.email} and supplied password."
        )

    def get(self, context: AuthedServiceContext, uid: UID) -> Result[SyftObject, str]:
        return self.stash.get_by_uid(uid)

    def signup(
        self, context: UnauthedServiceContext, user_update: UserUpdate
    ) -> Result[SyftObject, str]:
        pass

    # @service_method(path="user.search", name="search", splat_kwargs_from=["query_obj"])
    # def search(self, context: AuthedServiceContext, query_obj: UserQuery, limit: int):
    #     pass
