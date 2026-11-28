# Generic
import logging

# Libs
from flask import current_app, request
from flask_restx import Resource, abort

# Own
from baking.main import api
from baking.main.repository import get_repository
from baking.main.v1.endpoints.artificial_songs import TOO_MANY_GENERATIONS, abort_if_generating_too_much
from baking.main.v1.models import generator
from baking.main.v1.parsers import page_of, pagination_arguments
from baking.main.v1.serializers import artificial_title, page_of_artificial_titles

logger = logging.getLogger('baking-api')
ns = api.namespace('artificial_titles', description='Operations related to artificially generated titles')


@ns.route('/')
class ArtificialTitleCollection(Resource):

    @api.expect(pagination_arguments)
    @ns.marshal_with(page_of_artificial_titles)
    def get(self):
        """
        Returns a page of generated titles, most recent first.
        """
        args = pagination_arguments.parse_args(request)
        page, per_page = args.get('page', 1), args.get('per_page', 10)
        titles, total = get_repository().page_titles(page, per_page)
        return page_of(titles, total, page, per_page)


@ns.route('/generate/<lang>/song/<int:song_id>/')
@ns.response(404, 'Artificial song not found.')
@ns.response(429, TOO_MANY_GENERATIONS)
@ns.response(500, 'Internal server error.')
@ns.response(503, 'ML models are not loaded.')
class ArtificialTitleItem(Resource):

    @ns.marshal_with(artificial_title)
    def get(self, song_id, lang='en'):
        """
        Returns a generated title for the required lang and song_id.
        """
        if lang != 'en':
            abort(400, 'Artificial Titles can only be generated in english')

        repository = get_repository()
        generated = repository.get_generated_song(song_id)
        if generated is None:
            abort(404, 'Artificial song does not exist.')

        service = generator.get_service(current_app)
        if not service.settings.enabled:
            abort(503, 'ML models are not loaded')
        abort_if_generating_too_much()

        # The title is written in the style of the artist the song was generated for
        artist = generated.get('base_artist')

        try:
            title_text, _ = service.generate_title(generated['lyrics'] or '', artist['name'] if artist else None)
        except generator.ModelUnavailable:
            title_text = None  # already logged by the service; abort outside the handler to keep the log short
        if title_text is None:
            abort(503, 'ML models are not loaded')

        return repository.create_title(title_text or 'Untitled')
