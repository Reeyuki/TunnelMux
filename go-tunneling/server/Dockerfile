# Build stage
FROM golang:1.25-alpine AS builder

WORKDIR /app
COPY . .

RUN go mod init tunnelserver || true
RUN go mod tidy
RUN go build -o server .

FROM alpine:3.18

WORKDIR /app
COPY --from=builder /app/server /app/server

EXPOSE 8080
CMD ["/app/server"]
