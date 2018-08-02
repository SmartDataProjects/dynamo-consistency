pipeline {
  agent any
  environment {
    OPSSPACE_URL = 'https://github.com/CMSCompOps/OpsSpace.git'
    OPSSPACE_BRANCH = 'v0.7'
    VENV = 'source venv/bin/activate'
    TRAVIS = 'true'
  }
  stages {
    stage('Virtual Env') {
      steps {
        sh 'ls'
        sh 'if [ -d venv ]; then rm -rf venv; fi'
        sh '/home/jenkins/python/bin/virtualenv -p /usr/bin/python venv'
        sh 'ls'
      }    
    }
    stage('Build') {
      steps {
        sh 'ls'
        sh '$VENV; pip install "astroid<1.3" "pylint<1.4" "pyyaml==3.11"'
        sh 'if [ -d OpsSpace ]; then rm -rf OpsSpace; fi'
        sh 'git clone $OPSSPACE_URL; cd OpsSpace; git checkout $OPSSPACE_BRANCH'
        sh 'ls'
      }
    }

    stage('Test') {
      steps {
        sh '$VENV; OpsSpace/test/package_test.sh'
      }
    }
  }
}
