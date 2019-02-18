
# Continuous Integration QuickStart

The `ox_herd` package can be used as a simple, lightweight, continuous
integration server to automatically test all of your pull requests on
github. With just a few steps, you can have a continous integration server automatically running tests on each pull request created on your github project. 

To set things up, do the following:

  1. In a shell execute `git clone https://github.com/aocks/ox_herd.git && cd ox_herd`
  2. Define the following environment variables:
     - `GITHUB_USER`: Name of the user that Ox Herd will use to access github (e.g., `# export GITHUB_USER=test_user`).
     - `GITHUB_TOKEN`: Password or personal access token to access github.
     - `GITHUB_SECRET`: A secret string that the github webhook will
        use to authenticate to your server (more on this below).
  3. In a shell execute `docker-compose up` to create the docker image. Docker will buld the image and start the ox_herd server. The only thing left to do is configure github or some other system to ping it as shown below.
  4. As shown in the image below, go to the `Settings-->Webhooks` for your github project (e.g., go to `https://github.com/<owner>/<repo>/settings/hooks`), click `Add webhook`, and enter the following:
     - Payload URL: `http://www.example.com:6617/ox_herd/pytest` where you replace `www.example.com` with the domain name of the server you are running `ox_herd` on.
     - Content type: Set this to `application/json`.
     - Secret: enter in the secret string you used above for `GITHUB_SECRET`. This ensures that the `ox_herd` server and github share a secret so ox_herd will only respond to valid requests from github.
     - For "Which events would you like to trigger this webhook?" select "Let me select individual events." and select "Pull Reqest".

![How to setup github webhook](https://github.com/aocks/ox_herd/blob/master/docs/images/webhook_setup.png)

Provided port 6617 is open on your server, that's it! Now whenever you create a pull request on github, the github webhook sends a request to your ox_herd continuous integration server to run py.test on your code base. The results of running py.test will then be posted back to your pull request on github with the results.

## An important note on security

Keep in mind that while continous integraton is great, it requires some level of trust. In particular, anytime someone submits a pull request the continous integration server will run all those tests. So if someone created some malicious code in your tests they could cause your continuous intergration server to run that arbitrary code.

You have some protection from this in that your continous integration server is running in a docker image. But an attacker could still do things like:

  1. Get access to the `GITHUB_TOKEN` variable on your docker image.
  2. Cause your docker image to become a bot-net.
  3. Cause your docker image to consume a lot of resources.

So running a continous integration server like this is best suited to private github repositories where you trust the users and **NOT** a public github repo. For a public repo, using something like [Travis-CI](https://travis-ci.org/) is a good choice. You can also use [Travis-CI](https://travis-ci.org/) for a private repo but you need to pay a significant fee since [Travis-CI](https://travis-ci.org/) has a lot of nice features and is pretty heavyweight.

Some advantages of ox_herd are that it is free, open source, lightweight (so you can easily modify it or see what it is doing), and easy to setup.

# Additional features

You can view or interact with the ox_herd server directly provided you setup some kind of authentication. If you use ox_herd as a flask blueprint, you can configure authentication however you like. If you are using ox_herd in stand-alone mode, the easist thing to do is use the stub login features. You can do this in one of two ways:

  1. Provide user information when building the docker image. To do this, you should set the following environment variables before running `docker-compose up` or you can set them and rebuild the docker image:
     - OX_WEB_USER: Set this environment variable to the name of the user to interact with ox_herd.
     - OX_PASSWD_HASH: Set this to the password hash from the python passlib application. If your password is `<YOUR_PASSWORD>`, you can do this via the following python one-liner:
       ```
         export OX_PASSWD_HASH=`python3 -c 'from passlib.apps import custom_app_context; print( custom_app_context.encrypt("<YOUR_PASSWORD>"))'`
       ```
  2. Alternatively, you can just add a "user = password_hash" line to the `[STUB_USER_DB]` section of the configuration file of a running ox_herd server. You can do this via:
     - `docker exec -it ox_server /bin/bash` to get a shell on the docker image running the server
     - Get your hashed password using the python one liner shown previously.
     - Do `nano /home/ox_user/.ox_herd_conf` to edit the conf file and add a line like `<user> = <hashed_password>` in the `[STUB_USER_DB]` section.

# Configuration files

Instead of using environment variables, you can also put many of the
above parameters into your `~/.ox_herd_conf` for the user running the
ox_herd server.

```
[pytest/DEFAULT]
github_user = <username>
github_token = <token>
github_secret = <secret>

[STUB_USER_DB]

# Below you can put <username> = <hashed_password> for allowed
# ox_herd users. You can generate the hashed password via the following
# from a python3 session:
#
#    from passlib.apps import custom_app_context
#    print( custom_app_context.encrypt("<YOUR_PASSWORD>"))
tester = FIXME_put_hash_password_here
```
