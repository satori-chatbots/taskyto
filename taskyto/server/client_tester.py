import requests

import sys

def test_client():
    url = 'http://localhost:5000/hello'
    url = 'http://localhost:5000/msg'
    # url = 'http://localhost:5000/off'
    # url = 'http://localhost:5000/on'

    data = {'message': 'Yes, I want a big pizza'}
    
    if len(sys.argv)>1:
        data = {'message': sys.argv[1]}

    response = requests.post(url, json=data)
    # print(response.json())
    print(response.text)

def main():
    test_client()

if __name__ == '__main__':
    main()