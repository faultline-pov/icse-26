export WORKSPACE_BASE=$(dirname "$(realpath $0)")/../..
export PATH=$PATH:$WORKSPACE_BASE/java-env/apache-maven-3.5.0/bin:$WORKSPACE_BASE/java-env/jdk1.8.0_202/bin
export JAVA_HOME=$WORKSPACE_BASE/java-env/jdk1.8.0_202
export PATH=$PATH:$JAVA_HOME/bin
mvn clean package -B -V -e -Dfindbugs.skip -Dcheckstyle.skip -Dpmd.skip=true -Dspotbugs.skip -Denforcer.skip -Dmaven.javadoc.skip -DskipTests -Dmaven.test.skip.exec -Dlicense.skip=true -Drat.skip=true -Dspotless.check.skip=true -Dorg.slf4j.simpleLogger.log.org.apache.maven.cli.transfer.Slf4jMavenTransferListener=warn
