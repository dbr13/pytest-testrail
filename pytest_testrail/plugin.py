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
GET_TESTRUNS_URL = 'get_runs/{}'
GET_TESTCASES_ID_URL = 'get_tests/{}'
GET_TESTRUN_URL = 'get_run/{}'

TEST_LIST = []


def testrail(*ids):
    """
    Decorator to mark tests with testcase ids.
    It feryfies TEST_LIST for skipping tests

    Note: currently if we add more then on csae_id
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
    ids = tuple(map(lambda id: id, idds))
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


# def get_run_keys(items):
#     """Return Run case ids from Testrail"""
#     testcasesids = []


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
        tr_keys = get_testrail_keys(items)
        if self.testrun_name is None:
           #self.testrun_name = testrun_name()
            self.get_tests_from_run(run_id=self.run_id)                   # need to add globally

        else:
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
        response = self.client.send_get(
            GET_TESTCASES_ID_URL.format(run_id),
            self.cert_check
        )
        self.tests_list_id = [test['case_id'] for test in response]

        self.testrun_id = self.run_id



    # def get_tests_cases(self, runs_id_list):
    #
    #     """
    #     Get tests cases ids for incompleted runs
    #     :param runs_id_list:
    #     :return: dict key=run_id, val=list_of_cases for run
    #     """
    #
    #     run_tests = {}
    #
    #     for run_id in runs_id_list:
    #         _run_id = run_id['id']
    #
            #data = {'run_id':_run_id}
            #
            # respons = self.client.send_get(
            #     GET_TESTCASES_ID_URL.format(_run_id, self.cert_check)
            # )
            # tests = [test ['id'] for test in respons]
            # run_tests[_run_id] = test
        #
        # return run_tests

    # def get_test_runs(
    #         self, project_id, milestone_id, is_completed):
    #     """
    #     Get incompleted test runs
    #     :param project_id: 1 to return completed test runs only. 0 to return active test runs only.
    #     :param milestone_id:
    #     :param is_completed: 0 - to return active test runs
    #     :return:
    #     """
    #     data = {
    #         'milestone_id': milestone_id,
    #         'is_completed': is_completed
    #     }
    #
    #     response = self.client.send_get(
    #         GET_TESTRUNS_URL.format(project_id),
    #         data,
    #         self.cert_check
    #     )
    #     for key, _ in response.items():
    #         if key == 'error':
    #             print('Faild to get test_runs: {}'.format(response))
    #         else:
    #             return response

