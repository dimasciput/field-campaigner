__author__ = 'Irwan Fathurrahman <irwan@kartoza.com>'
__date__ = '10/05/17'

import bisect
import copy
import json
import os
import pygeoj
import time
from shapely import geometry as shapely_geometry
import campaign_manager.insights_functions as insights_functions
from flask import render_template
from campaign_manager.models.json_model import JsonModel
from campaign_manager.utilities import module_path


class Campaign(JsonModel):
    """
    Class campaign model that hold campaign information and functions.
    """
    uuid = ''
    name = ''
    campaign_creator = ''
    campaign_status = ''
    coverage = {}
    geometry = None
    start_date = None
    end_date = None
    campaign_managers = []
    selected_functions = []
    tags = []
    description = ''
    _content_json = None

    def __init__(self, uuid):
        self.uuid = uuid
        self.json_path = Campaign.get_json_file(uuid)
        self.edited_at = time.ctime(os.path.getmtime(self.json_path))
        self.parse_json_file()

    def save(self, uploader):
        """Save current campaign

        :param uploader: uploader who created
        :type uploader: str
        """
        self.version += 1
        self.edited_by = uploader
        # save updated campaign to json
        data = self.to_dict()
        Campaign.validate(data, self.uuid)
        json_str = Campaign.serialize(data)
        json_path = os.path.join(
            Campaign.get_json_folder(), '%s.json' % self.uuid
        )
        _file = open(json_path, 'w+')
        _file.write(json_str)
        _file.close()

    def update_data(self, data, uploader):
        """ Update data with new dict.

        :param data: data that will be inserted
        :type data: dict

        :param uploader: uploader who created
        :type uploader: str
        """
        for key, value in data.items():
            setattr(self, key, value)
        self.geometry = json.loads(self.geometry)
        self.selected_functions = json.loads(self.selected_functions)
        self.save(uploader)

    def get_selected_functions_in_string(self):
        """ Get selected function in string
        :return: Get selected function in string
        :rtype: str
        """
        for key, value in self.selected_functions.items():
            SelectedFunction = getattr(
                insights_functions, value['function'])
            selected_function = SelectedFunction(
                    self,
                    feature=value['feature'],
                    required_attributes=value['attributes'])
            value['manager_only'] = selected_function.manager_only
            value['name'] = selected_function.name()
        return json.dumps(self.selected_functions).replace('None', 'null')

    def parse_json_file(self):
        """ Parse json file for this campaign.

        If file is corrupted,
        it will raise Campaign.CorruptedFile exception.
        """
        if self.json_path:
            try:
                _file = open(self.json_path, 'r')
                content = _file.read()
                content_json = json.loads(content)
                Campaign.validate(content_json, self.uuid)
                self._content_json = content_json
                attributes = self.get_attributes()
                for key, value in content_json.items():
                    if key in attributes:
                        setattr(self, key, value)
            except json.decoder.JSONDecodeError:
                raise JsonModel.CorruptedFile

    def json(self):
        """Returns campaign as json format."""
        return self._content_json

    def render_insights_function(
            self,
            insight_function_id,
            additional_data={}):
        """Get rendered UI from insight_function

        :param insight_function_id: name of insight function
        :type insight_function_id: str

        :param additional_data: additional data that needed
        :type additional_data:dict

        :return: rendered UI from insight function
        :rtype: str
        """
        campaing_ui = ''
        try:
            function = self.selected_functions[insight_function_id]
            SelectedFunction = getattr(
                insights_functions, function['function'])
            additional_data['function_id'] = insight_function_id
            selected_function = SelectedFunction(
                self,
                feature=function['feature'],
                required_attributes=function['attributes'],
                additional_data=additional_data
            )
        except AttributeError as e:
            return campaing_ui

        # render UI
        context = {
            'selected_function_name': selected_function.name().split('-')[0],
            'icon': selected_function.icon,
            'widget': selected_function.get_ui_html()
        }
        campaing_ui += render_template(
            'campaign_widget/insight_template.html',
            **context
        )
        return campaing_ui

    def insights_function_data_metadata(self, insight_function_id):
        """Get rendered UI from insight_function

        :param insight_function_id: name of insight function
        :type insight_function_id: str

        :return: rendered UI from insight function
        :rtype: str
        """
        try:
            function = self.selected_functions[insight_function_id]
            SelectedFunction = getattr(
                insights_functions, function['function'])
            selected_function = SelectedFunction(
                self,
                feature=function['feature'],
                required_attributes=function['attributes'])
            return selected_function.metadata()
        except AttributeError as e:
            return {}

    def corrected_coordinates(self):
        """ Corrected geometry of campaign.
        :return: corrected coordinated
        :rtype: [str]
        """
        coordinates = self.geometry['features'][0]
        coordinates = coordinates['geometry']['coordinates'][0]
        correct_coordinates = []
        for coordinate in coordinates:
            correct_coordinates.append(
                [coordinate[1], coordinate[0]]
            )
        return correct_coordinates

    def get_bbox(self):
        """ Corrected geometry of campaign.
        :return: corrected coordinated
        :rtype: [str]
        """
        if not self.geometry:
            return []

        geometry = copy.deepcopy(self.geometry)
        geometry['features'][0]['geometry']['coordinates'][0] = \
            self.corrected_coordinates()
        geojson = pygeoj.load(data=geometry)
        return geojson.bbox

    # ----------------------------------------------------------
    # coverage functions
    # ----------------------------------------------------------
    def get_coverage_folder(self):
        """ Return coverage folder for this campaign
        :return: path for coverage folder
        :rtype: str
        """
        return os.path.join(
            module_path(),
            'campaigns_data',
            'coverage',
            self.uuid
        )

    @staticmethod
    def get_json_folder():
        return os.path.join(
            module_path(), 'campaigns_data', 'campaign')

    @staticmethod
    def serialize(data):
        """Serialize campaign dictionary

        :key data: dictionary
        :type data: dict
        """
        try:
            data['start_date'] = data['start_date'].strftime('%Y-%m-%d')
        except AttributeError:
            pass
        try:
            if data['end_date']:
                data['end_date'] = data['end_date'].strftime('%Y-%m-%d')
        except AttributeError:
            pass
        json_str = json.dumps(data)
        return json_str

    @staticmethod
    def create(data, uploader):
        """Validate found dict based on campaign class.
        uuid should be same as uuid file.

        :param data: data that will be inserted
        :type data: dict

        :param uploader: uploader who created
        :type uploader: str
        """
        data['version'] = 1
        data['edited_by'] = uploader
        data['campaign_creator'] = uploader

        uuid = data['uuid']
        Campaign.validate(data, uuid)
        data['geometry'] = json.loads(data['geometry'])
        data['selected_functions'] = json.loads(data['selected_functions'])

        json_str = Campaign.serialize(data)
        json_path = os.path.join(
            Campaign.get_json_folder(), '%s.json' % uuid
        )
        _file = open(json_path, 'w+')
        _file.write(json_str)
        _file.close()

    @staticmethod
    def all(**kwargs):
        """Get all campaigns

        :return: Campaigns that found or none
        :rtype: [Campaign]
        """
        name_list = []
        campaigns = []
        for root, dirs, files in os.walk(Campaign.get_json_folder()):
            for file in files:
                try:
                    campaign = Campaign.get(os.path.splitext(file)[0])
                    allowed = True
                    if kwargs:
                        campaign_dict = campaign.to_dict()
                        for key, value in kwargs.items():
                            if key not in campaign_dict:
                                allowed = False
                            elif value not in campaign_dict[key]:
                                allowed = False
                    if allowed:
                        position = bisect.bisect(name_list, campaign.name)
                        bisect.insort(name_list, campaign.name)
                        campaigns.insert(position, campaign)
                except Campaign.DoesNotExist:
                    pass
        return campaigns

    @staticmethod
    def nearest_campaigns(coordinate, **kwargs):
        """Return nearest campaigns based on coordinate

        :param coordinate: lat, long coordinate string
        :type coordinate: str
        """
        campaigns = []
        point = shapely_geometry.Point(
                [float(x) for x in coordinate.split(',')])
        distance = 3
        circle_buffer = point.buffer(distance)

        for root, dirs, files in os.walk(Campaign.get_json_folder()):
            for file in files:
                try:
                    campaign = Campaign.get(os.path.splitext(file)[0])
                    #
                    polygon = shapely_geometry.Polygon(
                            campaign.corrected_coordinates())
                    if circle_buffer.contains(polygon):
                        campaign_dict = campaign.to_dict()
                        allowed = True
                        if kwargs:
                            for key, value in kwargs.items():
                                if key not in campaign_dict:
                                    allowed = False
                                elif value not in campaign_dict[key]:
                                    allowed = False
                        if allowed:
                            campaigns.append(campaign)
                except Campaign.DoesNotExist:
                    pass

        return campaigns

    @staticmethod
    def get(uuid):
        """Get campaign from uuid

        :param uuid: UUID of campaign that to be returned
        :type uuid: str

        :return: Campaign that found or none
        :rtype: Campaign
        """
        return Campaign(uuid)

    @staticmethod
    def get_json_file(uuid):
        """ Get path of json file of uuid.
        :param uuid: UUID of json model that to be returned
        :type uuid: str

        :return: path of json or none if not found
        :rtype: str
        """
        json_path = os.path.join(
            Campaign.get_json_folder(), '%s.json' % uuid
        )
        if os.path.isfile(json_path):
            return json_path
        else:
            raise Campaign.DoesNotExist()

    @staticmethod
    def validate(data, uuid):
        """Validate found dict based on campaign class.
        uuid should be same as uuid file.

        :param data: data that will be inserted
        :type data: dict

        :param uuid: UUID of campaign
        :type uuid: str
        """
        required_attributes = [
            'uuid', 'version', 'campaign_creator', 'edited_by', 'name']
        for required_attribute in required_attributes:
            if required_attribute not in data:
                raise JsonModel.RequiredAttributeMissed(required_attribute)
            if uuid != data['uuid']:
                raise Exception('UUID is not same in json.')
        return True

    @staticmethod
    class DoesNotExist(Exception):
        def __init__(self):
            self.message = "Campaign doesn't exist"
            super(Campaign.DoesNotExist, self).__init__(self.message)

    @staticmethod
    class InsightsFunctionNotAssignedToCampaign(Exception):
        def __init__(self):
            self.message = "" \
                           "This insights function not " \
                           "assigned to this campaign"
            super(
                Campaign.InsightsFunctionNotAssignedToCampaign, self).__init__(
                self.message)
