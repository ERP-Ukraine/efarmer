# See LICENSE file for full copyright and licensing details.

from .base import GqlDict, CreateMixin, UpdateMixin
from ..exceptions import ShopifyApiError


class File(GqlDict, CreateMixin, UpdateMixin):
    """This is an GQL Interface, not a real object."""

    _gid_name = 'File'
    _body = GqlDict._tmpl.FILE_BODY

    MUTATION_CREATE = ''
    MUTATION_UPDATE = GqlDict._tmpl.MUTATION_FILE_UPDATE

    @property
    def name(self):
        self.ensure_one()
        return self.src.split('/')[-1]

    @property
    def src(self):
        self.ensure_one()
        return self._extract(self.to_dict(), 'preview.image.url', '') or ''

    @property
    def file_status(self):
        self.ensure_one()
        return self._env.FileStatus(self['fileStatus'])

    @property
    def file_errors(self):
        self.ensure_one()
        return self['fileErrors']

    @property
    def is_not_ready(self):
        self.ensure_one()
        return not self.file_status.is_ready

    @property
    def media_image_gid(self):
        self.ensure_one()
        return self._env.MediaImage.create_gid(self.id)

    def create(self, filename: str, mimetype: str, binary_data: bytes):
        # 1. Create staged upload target
        stage = self._env.StagedUploadTarget.create(filename, mimetype)

        # 2. Upload binary data
        stage._upload_binary_data(binary_data)

        # 3. Create file
        media_file = stage._create_file()

        errors = media_file.file_errors
        if errors:
            e = errors[0]
            raise ShopifyApiError(
                f'{e.code}: message={e.message}; details={e.details}'
            )

        return media_file

    def update(self, product_id: str) -> None:
        self.ensure_one()

        response = self._env.execute(
            self.MUTATION_UPDATE,
            variables={
                'input': {
                    'id': self.media_image_gid,
                    'referencesToAdd': [self._env.Product.create_gid(product_id)],
                },
            },
            user_errors_path='data.fileUpdate.userErrors',
        )

        values = self._extract(response, 'data.fileUpdate.files.0', dict)

        return self.set(**values)

    def _read(self, file_type: str = 'MediaImage'):
        """Redefined due to the `file_type` argument."""
        self.ensure_one()

        schema = self._get_base_schema()
        gid = self.create_gid(self.id).replace(self._gid_name, file_type)

        response = self._env.execute(schema, variables={'id': gid})
        data = self._extract(response, 'data.node', dict)

        self.set(**data)
