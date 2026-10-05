FROM golang:1.25.5-alpine AS build
ARG TARGETARCH
RUN apk add --no-cache git
WORKDIR /src
RUN git clone https://github.com/bdellegrazie/git-credential-github-app.git . \
    && git checkout 44092188bcdbbc209317424429489b2335793617
RUN go mod vendor
RUN CGO_ENABLED=0 GOOS=linux GOARCH=${TARGETARCH} go build -mod=vendor -trimpath -o /helper .

FROM alpine:3.23
COPY --from=build /helper /git-credential-github-app
COPY --from=build /src/LICENSE /usr/share/licenses/github-app/LICENSE
COPY --from=build /src/vendor /usr/share/github-mirror/vendor
ENTRYPOINT ["/git-credential-github-app"]
