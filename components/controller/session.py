import logging
import functools
import base64
import json
from json import JSONDecodeError
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning # pylint: disable=import-error


# Development systems and Sandboxes frequently have dynamically generated self-signed certificates
# Suppress HTTPS / SSL-related error messages
requests.packages.urllib3.disable_warnings(InsecureRequestWarning) # pylint: disable=no-member


class ControllerSession:
    def __init__(self, endpoint, **kwargs):
        self.endpoint = endpoint
        kwargs.setdefault('trust_env', False)
        kwargs.setdefault('verify', False)
        self.session = requests.Session()
        self.session.trust_env = kwargs.get('trust_env')
        self.session.verify = kwargs.get('verify')

    @property
    def basic_auth(self):
        return None

    @property
    def bearer_auth(self):
        return None

    @basic_auth.setter
    def basic_auth(self, credentials):
        try:
            user, password = credentials
        except ValueError as e: # pylint: disable=invalid-name
            logging.error(('Failed to set the Basic Authorization header. '
                           'Expected an iterable with two items (user, password)'), exc_info=e)
            raise
        else:
            self.session.headers['Authorization'] = ''
            encoded_credentials = str(base64.b64encode(
                f'{user}:{password}'.encode('utf-8')), 'utf-8')
            authorization = f'Basic {encoded_credentials}'
            self.session.headers['Authorization'] = authorization

    @bearer_auth.setter
    def bearer_auth(self, token):
        self.session.headers['Authorization'] = ''
        authorization = f'bearer {token}'
        self.session.headers['Authorization'] = authorization

    def handle_request(request_func):
        @functools.wraps(request_func)
        def send_request(*args, **kwargs):
            kwargs.setdefault('data', {})
            kwargs.setdefault('params', {})
            kwargs.setdefault('json', {})
            response = request_func(*args, **kwargs)
            return response
        return send_request

    def parse_response(handler_func):
        @functools.wraps(handler_func)
        def parse_response(*args, **kwargs):
            raw_response = handler_func(*args, **kwargs)
            parsed_response = {}
            if raw_response.text:
                try:
                    # Try to interpret the response as a normal JSON response body
                    parsed_response = json.loads(raw_response.text)
                except JSONDecodeError:
                    try:
                        # Try to interpret the response as an unconvensional multiline list
                        # of JSON strings
                        # Such responces are provided by Jobs API /observe
                        parsed_response = {
                            'responses': []
                        }
                        responses = raw_response.text.splitlines()
                        for response in responses:
                            response = json.loads(response)
                            parsed_response['responses'].append(response)
                    except JSONDecodeError:
                        try:
                            # Try to interpret the response as a list of plain text strings,
                            # e.g., as an application log
                            # Such responces are provided by logs API /logs
                            parsed_response = []
                            responses = raw_response.text.splitlines()
                            for response in responses:
                                parsed_response.append(response)
                        except Exception as e: # pylint: disable=invalid-name
                            logging.error(('Failed to parse the response body received from '
                                           f'{raw_response.url} with HTTP '
                                           f'{raw_response.status_code}: '
                                           f'{raw_response.text}'), exc_info=e)
                            raise
            else:
                logging.debug(('Empty response body received '
                               f'from {raw_response.url} with HTTP {raw_response.status_code}'))

            return {'response_body': parsed_response,
                    'response_headers': raw_response.headers,
                    'http_status': raw_response.status_code}
        return parse_response

    @handle_request
    @parse_response
    def get(self, path, **kwargs):
        try:
            logging.debug(f'Executes the HTTP GET request to {self.endpoint + path}')
            raw_response = self.session.get(self.endpoint + path, **kwargs)
        except Exception as e: # pylint: disable=invalid-name
            logging.error(f'Failed to send the HTTP GET to {self.endpoint + path}', exc_info=e)
            raise
        else:
            logging.debug((f'The HTTP GET request to {self.endpoint + path} '
                           f'received the response {raw_response}'))
            return raw_response

    @handle_request
    @parse_response
    def post(self, path, **kwargs):
        try:
            logging.debug(f'Executes the HTTP POST request to {self.endpoint + path}')
            raw_response = self.session.post(self.endpoint + path, **kwargs)
        except Exception as e: # pylint: disable=invalid-name
            logging.error(f'Failed to send the HTTP POST to {self.endpoint + path}', exc_info=e)
            raise
        else:
            logging.debug((f'The HTTP POST request to {self.endpoint + path} '
                           f'received the response {raw_response}'))
            return raw_response

    @handle_request
    @parse_response
    def put(self, path, **kwargs):
        try:
            logging.debug(f'Executes the HTTP PUT request to {self.endpoint + path}')
            raw_response = self.session.put(self.endpoint + path, **kwargs)
        except Exception as e: # pylint: disable=invalid-name
            logging.error(f'Failed to send the HTTP PUT to {self.endpoint + path}', exc_info=e)
            raise
        else:
            logging.debug((f'The HTTP PUT request to {self.endpoint + path} '
                           f'received the response {raw_response}'))
            return raw_response

    @handle_request
    @parse_response
    def delete(self, path, **kwargs):
        try:
            logging.debug(f'Executes the HTTP DELETE request to {self.endpoint + path}')
            raw_response = self.session.delete(self.endpoint + path, **kwargs)
        except Exception as e: # pylint: disable=invalid-name
            logging.error(f'Failed to send the HTTP DELETE to {self.endpoint + path}', exc_info=e)
            raise
        else:
            logging.debug((f'The HTTP DELETE request to {self.endpoint + path} '
                           f'received the response {raw_response}'))
            return raw_response
