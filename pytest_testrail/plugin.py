from datetime import datetime
import pytest


PYTEST_TO_TESTRAIL_STATUS = {
    "passed": 1,
    "failed": 5,
    "skipped": 2,
    "n/a": 7
}

DT_FORMAT = '%d-%m-%Y %H:%M:%S'

TESTRAIL_PREFIX = 'testrail'

ADD_RESULTS_URL = 'add_results_for_cases/{}/'
ADD_TESTRUN_URL = 'add_run/{}'
GET_TESTCASES_ID_URL = 'get_tests/{}'


TEST_LIST = []


def testrail(*ids):
    """
    Decorator to mark tests with testcase ids.
    It feryfies TEST_LIST for skipping tests

    Note: currently if we add more then on case_id
    and some of them will be merked skipped this test will skipped totally
    ie. @testrail('C123', 'C12345')

    :return pytest.mark:
    """
    global TEST_LIST
    idds = []
    for idn in ids:
        if len(TEST_LIST) == 0 or idn in TEST_LIST:
            idds.append(idn)
        else:
            return pytest.mark.skip(msg='Test is out of run')
    ids = tuple(map(lambda idn: idn, idds))
    return pytest.mark.testrail(ids=ids)


def get_tests_list(client, run_id, cert):
    response = client.send_get(
        GET_TESTCASES_ID_URL.format(run_id),
        cert_check=cert
    )
    global TEST_LIST
    for test in response:
        TEST_LIST.append('C{}'.format(test['case_id']))
    return TEST_LIST


def get_test_outcome(outcome):
    """
    Return numerical value of test outcome.

    :param str outcome: pytest reported test outcome value.
    :returns: int relating to test outcome.
    """
    return PYTEST_TO_TESTRAIL_STATUS[outcome]


def testrun_name():
    """Returns testrun name with timestamp"""
    now = datetime.utcnow()
    return 'Automated Run {}'.format(now.strftime(DT_FORMAT))


def clean_test_ids(test_ids):
    """
    Clean pytest marker containing testrail testcase ids.

    :param list test_ids: list of test_ids.
    :return list ints: contains list of test_ids as ints.
    """
    return map(int, [test_id.upper().replace('C', '') for test_id in test_ids])


def get_testrail_keys(items):
    """Return TestRail ids from pytests markers"""
    testcaseids = []
    for item in items:
        if item.get_marker(TESTRAIL_PREFIX):
            testcaseids.extend(
                clean_test_ids(
                    item.get_marker(TESTRAIL_PREFIX).kwargs.get('ids')
                )
            )
    return testcaseids


class TestRailPlugin(object):
    def __init__(
            self, client, assign_user_id, project_id, suite_id, milestone_id, is_completed, cert_check, tr_name, run_id):
        self.assign_user_id = assign_user_id
        self.cert_check = cert_check
        self.client = client
        self.project_id = project_id
        self.results = []
        self.suite_id = suite_id
        self.testrun_id = 0
        self.milestone_id = milestone_id
        self.is_comleted = is_completed
        self.testrun_name = tr_name
        self.run_id = run_id

    # pytest hooks

    @pytest.hookimpl(trylast=True)
    def pytest_collection_modifyitems(self, session, config, items):
        #tr_keys = get_testrail_keys(items)
        if self.testrun_name is None:
           #self.testrun_name = testrun_name()
            self.get_tests_from_run(run_id=self.run_id)

        else:
            tr_keys = get_testrail_keys(items)
            self.create_test_run(
                self.assign_user_id,
                self.project_id,
                self.suite_id,
                self.testrun_name,
                self.milestone_id,
                tr_keys
            )

    @pytest.hookimpl(tryfirst=True, hookwrapper=True)
    def pytest_runtest_makereport(self, item, call):
        outcome = yield
        rep = outcome.get_result()
        if item.get_marker(TESTRAIL_PREFIX):
            testcaseids = item.get_marker(TESTRAIL_PREFIX).kwargs.get('ids')

            if rep.when == 'call' and testcaseids:
                self.add_result(
                    clean_test_ids(testcaseids),
                    get_test_outcome(outcome.result.outcome)
                )

    def pytest_sessionfinish(self, session, exitstatus):
        data = {'results': self.results}
        if data['results']:
            self.client.send_post(
                ADD_RESULTS_URL.format(self.testrun_id),
                data,
                self.cert_check
            )

    # plugin

    def add_result(self, test_ids, status):
        """
        Add a new result to results dict to be submitted at the end.

        :param list test_id: list of test_ids.
        :param int status: status code of test (pass or fail).
        """
        for test_id in test_ids:
            if self.tests_case_type_ids[test_id] == 10:
                data = {
                    'case_id': test_id,
                    'status_id': PYTEST_TO_TESTRAIL_STATUS['n/a']
                }
            else:
                data = {
                    'case_id': test_id,
                    'status_id': status,
                }
            self.results.append(data)

    def create_test_run(
            self, assign_user_id, project_id, suite_id, testrun_name, milestone_id, tr_keys):
        """
        Create testrun with ids collected from markers.

        :param list items: collected testrail ids.
        """
        data = {
            'suite_id': suite_id,
            'name': testrun_name,
            'assignedto_id': assign_user_id,
            'include_all': False,
            'milestone_id': milestone_id,
            'case_ids': tr_keys,
        }

        response = self.client.send_post(
            ADD_TESTRUN_URL.format(project_id),
            data,
            self.cert_check
        )
        for key, _ in response.items():
            if key == 'error':
                print('Failed to create testrun: {}'.format(response))
            else:
                self.testrun_id = response['id']

    def get_tests_from_run(self, run_id):
        """
        Create object's attribute dict {case_id: type_id}
        :param run_id:
        :return:
        """
        response = self.client.send_get(
            GET_TESTCASES_ID_URL.format(run_id),
            self.cert_check
        )
        self.tests_case_type_ids = {test['case_id']: test['type_id'] for test in response}

        self.testrun_id = self.run_id


