# See LICENSE file for full copyright and licensing details.

import requests

from .base import GqlDict, CreateMixin


class StagedUploadTarget(GqlDict, CreateMixin):

    _gid_name = 'StagedUploadTarget'

    MUTATION_CREATE = GqlDict._tmpl.MUTATION_CREATE_STAGED_TARGET
    MUTATION_FILE_CREATE = GqlDict._tmpl.MUTATION_FILE_CREATE

    def __bool__(self):
        return bool(self.url and self.src)

    @property
    def src(self):
        return self.resourceUrl

    def get_parameters(self):
        return {x['name']: x['value'] for x in (self['parameters'] or [])}

    def create(self, filename: str, mimetype: str):
        response = self._env.execute(
            self.MUTATION_CREATE,
            variables={
                'input': {
                    'filename': filename,
                    'mimeType': mimetype,
                    'resource': 'IMAGE',
                    'httpMethod': 'POST',
                }
            },
            user_errors_path='data.stagedUploadsCreate.userErrors',
        )

        result = self._extract(response, 'data.stagedUploadsCreate.stagedTargets.0', dict)

        return self._new(**result)

    def _upload_binary_data(self, binary_data: bytes):
        self.ensure_one()

        response = requests.post(
            self.url,
            files={'file': binary_data},
            data=self.get_parameters(),
        )

        return response.ok

    def _create_file(self, content_type: str = 'IMAGE'):
        self.ensure_one()

        response = self._env.execute(
            self.MUTATION_FILE_CREATE,
            variables={
                'files': {
                    'contentType': content_type,
                    'originalSource': self.src,
                }
            },
            user_errors_path='data.fileCreate.userErrors',
        )

        values = self._extract(response, 'data.fileCreate.files.0', dict)
        return self._env.File.set(**values)
