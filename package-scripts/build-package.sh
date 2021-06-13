#! /bin/bash

SCRIPTS_DIR='package-scripts'

######## This block only executes when you call this script outside of docker ########
if [[ -z "$BUILD_ENV" ]]; then
    echo "-------------------------------- BUILDING TEMPORARY IMAGE"
    IMAGE_ID=`docker build --force-rm -f ./${SCRIPTS_DIR}/.dockerfile -q .`
    echo "-------------------------------- STARTING CONTAINER"
    echo "-------------------------------- IMAGE ID: $IMAGE_ID"
    docker run --rm -it -e BUILD_ENV="docker" $IMAGE_ID /bin/bash "./${SCRIPTS_DIR}/build-package.sh"
    echo "-------------------------------- DELETING TEMPORARY IMAGE"
    docker rmi $IMAGE_ID

######## This block executes inside the docker container ########
else
    echo "-------------------------------- BEGINNING BUILD..."
    # Build python distribution package
    pip install twine
    python setup.py sdist

    # Upload built package to the repo
    twine upload --config-file .pypirc --repository spgill dist/*
    echo "-------------------------------- DONE!"
fi
