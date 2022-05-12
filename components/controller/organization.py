import logging
import json
from components.tools.utils import epoch_to_datetime # pylint: disable=import-error
from components.controller.space import Space # pylint: disable=import-error


class Organization:
    # pylint: disable=too-many-instance-attributes

    def __init__(self, controller, raw_data):
        try:
            logging.debug(f'Loading the organization information based on {raw_data}')

            self.controller = controller
            self.controller_session = self.controller.controller_session
            self.guid = raw_data.get('metadata').get('guid')
            self.name = raw_data.get('organizationEntity').get('name')
            self.state = raw_data.get('organizationEntity').get('state')
            self.created_at = epoch_to_datetime(raw_data.get('metadata').get('created_at'))
            self.updated_at = epoch_to_datetime(raw_data.get('metadata').get('updated_at'))

            # Lazy load the organization content
            self._spaces = {}

            logging.info((f'Loaded information about the organization {self.name} / {self.guid} '
                          'from Controller'))

        except Exception as e: # pylint: disable=invalid-name
            logging.error(
                f'Failed to instantiate organization by metadata {json.dumps(raw_data)}',
                exc_info=e)
            raise

    #
    # Lazy load the organization spaces
    #
    @property
    def spaces(self):
        return self._spaces

    @spaces.getter
    def spaces(self):
        controller_session = self.controller_session
        if not self._spaces:
            try:
                params = {'q': f'organization_guid:{self.guid}'}
                spaces_info = controller_session.get('/v2/spaces', params=params)
                spaces = spaces_info.get('response_body').get('spaces')
            except Exception as e: # pylint: disable=invalid-name
                logging.error(
                    f'Failed to fetch spaces for organization {self.name} / {self.guid}',
                    exc_info=e)
                raise
            else:
                parsed_spaces = {}
                for space in spaces:
                    space_guid = space.get('metadata').get('guid')
                    parsed_spaces[space_guid] = Space(self, space)
                self._spaces = parsed_spaces
                logging.debug(
                    f'Loaded information about spaces of organization {self.name} / {self.guid}')
        return self._spaces

    @spaces.setter
    def spaces(self, spaces):
        self._spaces = spaces

    #
    # Organization methods and helpers
    #
    @staticmethod
    def get_item_by_guid(entity: dict, guid):
        return next((entity[item] for item in entity if entity[item].guid == guid), None)

    @staticmethod
    def get_item_by_name(entity: dict, name):
        return next((entity[item] for item in entity if entity[item].name == name), None)

    def get_space_by_name(self, name):
        found_space = self.get_item_by_name(self.spaces, name)
        if not found_space:
            logging.warning(f'The space information is not found for name {name}')
        return found_space

    def get_space_by_guid(self, guid):
        found_space = self.get_item_by_guid(self.spaces, guid)
        if not found_space:
            logging.warning(f'The space information is not found for guid {guid}')
        return found_space
