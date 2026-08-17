#!/usr/bin/env bash
# Maven 执行脚本（WSL / Linux 下使用）
# 用法: ./mvnw-custom.sh <args...>
set -e
export JAVA_HOME="${JAVA_HOME:-/usr/lib/jvm/java-8-openjdk-amd64}"
export PATH="$JAVA_HOME/bin:$PATH"
MAVEN_HOME="${MAVEN_HOME:-/home/heart/tools/apache-maven-3.9.9}"
exec "$MAVEN_HOME/bin/mvn" "$@"
