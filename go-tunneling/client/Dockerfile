# Build stage
FROM golang:1.21-alpine AS builder

WORKDIR /app
COPY . .

RUN go mod init tunnelclient || true
RUN go mod tidy
RUN go build -o client .

FROM alpine:3.18

WORKDIR /app
COPY --from=builder /app/client /app/client


CMD ["/app/client"]
