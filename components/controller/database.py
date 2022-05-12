import logging

class Database:
    # pylint: disable=too-many-instance-attributes

    def __init__(self, controller, raw_data):
        logging.debug(f'Loading the database information based on {raw_data}')

        self.controller = controller
        self.hana_broker_session = self.controller.hana_broker_session
        self.guid = raw_data.get('id')
        self.tenant_name = raw_data.get('properties').get('tenant_name')
        self.encryption = raw_data.get('properties').get('encrypt')
        self.hana_broker_user = raw_data.get('user')
        self.xsa_hana_broker_schema = raw_data.get('hdiSchema')
        self.usergroups = raw_data.get('usergroups')
        self.jdbc_endpoint = raw_data.get('jdbcBaseUrl')

        self.mapped_orgs_space_guids = raw_data.get('mapped_orgs_space_guids')
        self.mapped_org_space_names = []
        for org_space in self.mapped_orgs_space_guids:
            org_guid, space_guid = org_space
            org = controller.get_org_by_guid(org_guid) if bool(org_guid) else None
            space = org.get_space_by_guid(space_guid) if bool(space_guid) else None
            org_name = org.name if org else ''
            space_name = space.name if space else ''
            mapping_name = f'{org_name}/{space_name}'
            self.mapped_org_space_names.append(mapping_name)

        self._invalid_instances = {}
        self._representation = None
        self._invalid_instances_representation = None

        logging.info((f'Loaded information about the database {self.tenant_name} / {self.guid} '
                      'from Controller'))

    #
    # Represent the database for Collector
    #
    @property
    def representation(self):
        return self._representation

    @representation.getter
    def representation(self):
        return (self.guid,
                self.tenant_name,
                self.encryption,
                self.hana_broker_user,
                self.xsa_hana_broker_schema,
                self.mapped_org_space_names,
                self.usergroups,
                self.jdbc_endpoint)

    @staticmethod
    def get_representation_keys():
        return ['GUID',
                'Tenant',
                'Encryption',
                'HANA Broker User',
                'HANA Broker Schema',
                'Mapped Orgs / Spaces',
                'DB Usergroups',
                'JDBC Endpoint']

    #
    # Lazy load the invalid HDI service instances
    #
    @property
    def invalid_instances(self):
        return self._invalid_instances

    @invalid_instances.getter
    def invalid_instances(self):
        hana_broker_session = self.hana_broker_session
        if not self._invalid_instances:
            try:
                invalid_instances_info = hana_broker_session.get(
                    f'/admin/invalid_instances/{self.guid}')
                invalid_instances = invalid_instances_info.get('response_body')
            except Exception as e: # pylint: disable=invalid-name
                logging.error(('Failed to load the invalid_instances '
                               f'of database {self.tenant_name} / {self.guid}'), exc_info=e)
                raise
            else:
                parsed_invalid_instances = {}
                for guid in invalid_instances:
                    try:
                        invalid_instance_info = self.hana_broker_session.get(
                            f'/admin/service_instances/{guid}')
                        invalid_instance = invalid_instance_info.get('response_body')
                    except Exception as e: # pylint: disable=invalid-name
                        logging.error(('Failed to load the information '
                                       f'about invalid service instance  / {guid}'), exc_info=e)
                        raise
                    else:
                        org_guid = invalid_instance.get('organization_guid')
                        space_guid = invalid_instance.get('space_guid')

                        org = self.controller.get_org_by_guid(org_guid)
                        space = org.get_space_by_guid(space_guid)

                        service_instance = space.get_service_instance_by_guid(guid)

                        parsed_invalid_instances[guid] = {'org' : org,
                                                          'space' : space,
                                                          'service_instance' : service_instance,
                                                          'error_message' : invalid_instances[guid]}
                self._invalid_instances = parsed_invalid_instances
        return self._invalid_instances

    @invalid_instances.setter
    def invalid_instances(self, invalid_instances):
        self._invalid_instances = invalid_instances
