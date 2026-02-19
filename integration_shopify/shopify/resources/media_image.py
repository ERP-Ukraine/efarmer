# See LICENSE file for full copyright and licensing details.

from .base import DeleteMixin
from .media import AbstractMedia


class MediaImage(AbstractMedia, DeleteMixin):

    _media_type = 'MediaImage'

    MUTATION_DELETE = AbstractMedia._tmpl.MUTATION_DELETE_FILES

    def delete(self):
        self.ensure_one()
        return self.delete_batch([self.gid])

    def delete_batch(self, file_ids: list):
        if not file_ids:
            return []

        response = self._env.execute(
            self.MUTATION_DELETE,
            variables={
                'input': [self.create_gid(x) for x in file_ids],
            },
            user_errors_path='data.fileDelete.userErrors',
        )

        return self._extract(response, 'data.fileDelete.deletedFileIds', list)
