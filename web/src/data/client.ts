import { IS_INTERNAL } from "../config";
import { internalClient } from "./internalClient";
import { publicClient } from "./publicClient";
import type { DataClient } from "./types";

export const dataClient: DataClient = IS_INTERNAL ? internalClient : publicClient;
export { internalClient, publicClient };
export * from "./types";
