// One in-flight measurement and at most the most recent pending snapshot.
export class LatestMeasurementQueue {
  #active = false;
  #pending = null;
  #disposed = false;

  submit(task) {
    if (this.#disposed) return;
    if (this.#active) {
      this.#pending = task;
      return;
    }
    this.#active = true;
    Promise.resolve().then(() => {
      if (!this.#disposed) return task();
    }).catch(() => {
      // The caller handles its own request errors; keep the queue usable.
    }).finally(() => {
      this.#active = false;
      const next = this.#pending;
      this.#pending = null;
      if (!this.#disposed && next) this.submit(next);
    });
  }

  dispose() {
    this.#disposed = true;
    this.#pending = null;
  }
}
