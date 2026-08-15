#!/usr/bin/env bash
# Maven 包装脚本（Windows Git Bash 下使用，规避 MSYS 路径问题）
# 用法: ./mvnw-custom.sh <args...>
export JAVA_HOME="C:\Program Files\Java\jdk1.8.0_261"
JAVACMD="C:\\Program Files\\Java\\jdk1.8.0_261\\bin\\java"
MAVEN_HOME_WIN="D:\\Maven\\apache-maven-3.9.9"
MAVEN_HOME_UNIX="/d/Maven/apache-maven-3.9.9"

exec "$JAVACMD" \
  -classpath "$MAVEN_HOME_WIN\\boot\\plexus-classworlds-2.8.0.jar" \
  "-Dclassworlds.conf=$MAVEN_HOME_WIN\\bin\\m2.conf" \
  "-Dmaven.home=$MAVEN_HOME_WIN" \
  "-Dmaven.repo.local=C:\\Users\\heart\\.m2\\repository" \
  "-Dmaven.multiModuleProjectDirectory=$(pwd)" \
  org.codehaus.plexus.classworlds.launcher.Launcher "$@"
