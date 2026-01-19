# ╔══════════════════════════════════════╗
# ║  NexusAgent Java 微服务通用镜像构建   ║
# ╚══════════════════════════════════════╝
# 用法: docker build --build-arg MODULE=nexus-auth -f Dockerfile.java .

FROM maven:3.9-eclipse-temurin-21-alpine AS builder

ARG MODULE

WORKDIR /build
COPY pom.xml .
COPY nexus-common/pom.xml nexus-common/pom.xml
COPY ${MODULE}/pom.xml ${MODULE}/pom.xml

# 先下载依赖（利用 Docker 层缓存）
RUN mvn dependency:go-offline -pl ${MODULE} -am -B -q || true

COPY nexus-common nexus-common
COPY ${MODULE} ${MODULE}

RUN mvn package -pl ${MODULE} -am -DskipTests -B -q \
    && mkdir -p /app \
    && cp ${MODULE}/target/*.jar /app/app.jar

# ── 运行阶段 ──
FROM eclipse-temurin:21-jre-alpine

LABEL maintainer="NexusAgent Team"

RUN addgroup -S app && adduser -S app -G app
WORKDIR /app
COPY --from=builder /app/app.jar .

USER app
EXPOSE 8080

ENTRYPOINT ["java", "-jar", "app.jar"]
