import requests
import json

from datetime import datetime


SINCE_DT = '2017-05-24T00:00:00Z'
TD_FORMAT = '%Y-%m-%dT%H:%M:%SZ'

def closed_pulls():
    params = {
        'state': 'closed',
        'base': 'develop',
    }
    since_date = datetime.strptime(SINCE_DT, TD_FORMAT) 
    response = requests.get('https://api.github.com/repos/ansible/ansible-container/pulls', params=params)
    for issue in response.json():
        closed_date = datetime.strptime(issue['closed_at'], TD_FORMAT)  
        if closed_date > since_date:
            print("- `{} {} <{}>`_".format(issue['number'], issue['title'], issue['html_url']))

def main():
    print("\nClosed pull requests:")
    closed_pulls()

if __name__ == '__main__':
    main()
