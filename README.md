# Plumber

A tool that deletes Bitbucket pipeline build steps that are now obsolete and opens a PR in the given repo.

## How do I get set up?

This tool requires 3 things to be done before being able to run the script.

### Dependencies

To install this script's dependencies, run the following command:  
`pip install -r requirements.txt`

### Environment variables

As this tool requires authentication to connect to the Bitbucket API, you will need to set 2 environment variables:
1. BB_USER_ID
2. BB_APP_PASS

### Configuration

Finally, this tool requires a JSON formatted configuration file. By default, it assumes the filepath to
be `./config.json`, but this can be changed using the `-c` argument.

The config file should be structured as follows:
```json
{
  "workspace": "<string>",
  "repositories": [
    "<string>"
  ],
  "steps": [
    {
      "name": "<string>",
      "files": [
        "<string>"
      ]
    }
  ],
  "reviewers": [
    {
      "account_id": "<string>"
    }
  ]
}
```
Use the following endpoint, replacing all values where needed, to find the account ids of each reviewer:  
https://bitbucket.org/!api/2.0/workspaces/<workspace_name>/members

# TODO 
- Refactor to utilize asyncio
- Use regex when finding build steps for deletion
- Add method of dynamically retrieving reviewer account ids
- Modify logic to create only one PR per repository if multiple steps are being removed