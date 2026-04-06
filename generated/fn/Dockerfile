FROM eclipse-temurin:21-jdk AS build
WORKDIR /build
COPY src ./src
RUN javac -d out $(find src -name '*.java') && \
    jar --create --file function.jar -C out .

FROM ubuntu:24.04
RUN apt-get update && apt-get install -y curl redis-tools ca-certificates bash && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=build /build/function.jar /app/function.jar
COPY george-jdk /opt/george-jdk
COPY bootstrap.sh /app/bootstrap.sh
RUN chmod +x /app/bootstrap.sh
ENV JAVA_HOME=/opt/george-jdk
ENV PATH=/opt/george-jdk/bin:$PATH
ENV PROFILE_PATH=/profiles/latest.mdox
ENV PROFILE_DUMP_PATH=/profiles/out.mdox
ENV ARTIFACT_KEY=__ARTIFACT_KEY__
ENV REDIS_HOST=redis.jit-system.svc.cluster.local
ENV REDIS_PORT=6379
ENV PORT=8080
CMD ["/app/bootstrap.sh"]
