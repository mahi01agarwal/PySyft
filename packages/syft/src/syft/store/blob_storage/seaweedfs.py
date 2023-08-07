# stdlib
from io import BytesIO
import math
from typing import List
from typing import Union

# third party
import boto3
from botocore.client import BaseClient as S3BaseClient
from botocore.client import ClientError as BotoClientError
from botocore.client import Config
import requests
from typing_extensions import Self

# relative
from . import BlobDeposit
from . import BlobRetrieval
from . import BlobRetrievalByURL
from . import BlobStorageClient
from . import BlobStorageClientConfig
from . import BlobStorageConfig
from . import BlobStorageConnection
from ...serde.serializable import serializable
from ...service.response import SyftError
from ...service.response import SyftException
from ...service.response import SyftSuccess
from ...types.blob_storage import BlobStorageEntry
from ...types.blob_storage import CreateBlobStorageEntry
from ...types.blob_storage import SecureFilePathLocation
from ...types.grid_url import GridURL
from ...types.syft_object import SYFT_OBJECT_VERSION_1
from ...types.uid import UID

READ_EXPIRATION_TIME = 1800  # seconds
WRITE_EXPIRATION_TIME = 900  # seconds
DEFAULT_CHUNK_SIZE = 1024  # GB


# def _byte_chunks(bytes: BytesIO, size: int) -> Generator[bytes]:
#     while True:
#         try:
#             yield bytes.read(size)
#         except BlockingIOError:
#             return


@serializable()
class SeaweedFSBlobDeposit(BlobDeposit):
    __canonical_name__ = "SeaweedFSBlobDeposit"
    __version__ = SYFT_OBJECT_VERSION_1

    urls: list[str]

    def write(self, data: bytes) -> Union[SyftSuccess, SyftError]:
        # relative
        from ...client.api import APIRegistry

        etags = []
        part_no = 1

        try:
            for byte_chunk, url in zip(
                BytesIO(data).read(DEFAULT_CHUNK_SIZE), self.urls
            ):
                response = requests.put(url=url, data=byte_chunk)
                response.raise_for_status()
                etag = response.headers["ETag"]
                etags.append({"ETag": etag, "PartNumber": part_no})
                part_no += 1
        except requests.HTTPError as e:
            return SyftError(message=f"{e}")

        api = APIRegistry.api_for(
            node_uid=self.syft_node_location,
            user_verify_key=self.syft_client_verify_key,
        )
        return api.services.blob_storage.mark_write_complete(
            etags=etags, uid=self.blob_storage_entry_id
        )


@serializable()
class SeaweedFSClientConfig(BlobStorageClientConfig):
    host: str
    port: int
    access_key: str
    secret_key: str
    region: str
    bucket_name: str

    @property
    def endpoint_url(self) -> str:
        grid_url = GridURL(host_or_ip=self.host, port=self.port)
        return grid_url.url


@serializable()
class SeaweedFSClient(BlobStorageClient):
    config: SeaweedFSClientConfig

    def connect(self) -> BlobStorageConnection:
        return SeaweedFSConnection(
            client=boto3.client(
                "s3",
                endpoint_url=self.config.endpoint_url,
                aws_access_key_id=self.config.access_key,
                aws_secret_access_key=self.config.secret_key,
                config=Config(signature_version="s3v4"),
                region_name=self.config.region,
            ),
            bucket_name=self.config.bucket_name,
        )


@serializable()
class SeaweedFSConnection(BlobStorageConnection):
    client: S3BaseClient
    bucket_name: str

    def __init__(self, client: S3BaseClient, bucket_name: str):
        self.client = client

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc) -> None:
        self.client.close()

    def read(self, fp: SecureFilePathLocation) -> BlobRetrieval:
        try:
            url = self.client.generate_presigned_url(
                ClientMethod="get_object",
                Params={"Bucket": self.bucket_name, "Key": fp.path},
                ExpiresIn=READ_EXPIRATION_TIME,
            )
            return BlobRetrievalByURL(url=url)
        except BotoClientError as e:
            raise SyftException(e)

    def allocate(self, obj: CreateBlobStorageEntry) -> SecureFilePathLocation:
        try:
            result = self.create_multipart_upload(
                Bucket=self.bucket_name,
                Key=str(obj.id),
            )
            upload_id = UID(result["UploadId"])
            return SecureFilePathLocation(id=upload_id, path=str(obj.id))
        except BotoClientError as e:
            raise SyftException(e)

    def write(self, obj: BlobStorageEntry) -> BlobDeposit:
        total_parts = math.ceil(obj.file_size / DEFAULT_CHUNK_SIZE)
        urls = []
        for part_no in range(total_parts):
            # Creating presigned urls
            signed_url = self.client.generate_presigned_url(
                ClientMethod="upload_part",
                Params={
                    "Bucket": self.bucket_name,
                    "Key": obj.location.path,
                    "UploadId": obj.location.id.value,
                    "PartNumber": part_no + 1,
                },
                ExpiresIn=WRITE_EXPIRATION_TIME,
            )
            urls.append(signed_url)

        return SeaweedFSBlobDeposit(urls=urls)

    def complete_multipart_upload(
        self,
        blob_entry: BlobStorageEntry,
        etags: List,
    ) -> Union[SyftError, SyftSuccess]:
        try:
            self.client.complete_multipart_upload(
                Bucket=self.bucket_name,
                Key=blob_entry.location.path,
                MultipartUpload={"Parts": etags},
                UploadId=blob_entry.location.id.to_string(),
            )
            return SyftSuccess("Successfully saved file.")
        except BotoClientError as e:
            return SyftError(f"{e}")


class SeaweedFSConfig(BlobStorageConfig):
    client_type = SeaweedFSClient
    client_config: SeaweedFSClientConfig
