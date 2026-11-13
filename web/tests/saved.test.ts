import { describe, expect, it } from "vitest";
import {
  SAVED_LIMIT,
  SAVED_STORAGE_KEY,
  buildSavedParam,
  isSaved,
  mergeSaved,
  parseSavedSlugs,
  readSavedList,
  toggleSaved,
  toSavedEntry,
  writeSavedList,
  type SavedEntry,
  type StorageLike,
} from "../src/lib/saved";

/** 브라우저 localStorage 대신 쓰는 최소 어댑터. */
function fakeStorage(initial: Record<string, string> = {}): StorageLike & { data: Record<string, string> } {
  const data = { ...initial };
  return {
    data,
    getItem: (k) => (k in data ? data[k] : null),
    setItem: (k, v) => {
      data[k] = v;
    },
    removeItem: (k) => {
      delete data[k];
    },
  };
}

const entry = (slug: string, n = slug): Omit<SavedEntry, "savedAt"> => ({
  slug,
  n,
  k: "skill",
  st: 100,
  sh: null,
});

describe("parseSavedSlugs", () => {
  it("빈 값은 빈 목록", () => {
    expect(parseSavedSlugs(null)).toEqual([]);
    expect(parseSavedSlugs("")).toEqual([]);
    expect(parseSavedSlugs("  ,  ,")).toEqual([]);
  });

  it("쉼표로 나누고 앞뒤 공백을 없앤다", () => {
    expect(parseSavedSlugs(" a/b , c/d ")).toEqual(["a/b", "c/d"]);
  });

  it("중복은 하나만 남는다", () => {
    expect(parseSavedSlugs("a/b,a/b,c/d")).toEqual(["a/b", "c/d"]);
  });

  it("퍼센트 인코딩을 풀어 원래 슬러그를 얻는다", () => {
    expect(parseSavedSlugs("a%2Fb,c%2Fd")).toEqual(["a/b", "c/d"]);
  });

  it("저장 한도를 넘으면 자른다", () => {
    const many = Array.from({ length: SAVED_LIMIT + 20 }, (_, i) => `s${i}`).join(",");
    expect(parseSavedSlugs(many)).toHaveLength(SAVED_LIMIT);
  });
});

describe("buildSavedParam", () => {
  it("슬러그를 각각 인코딩해 쉼표로 잇는다", () => {
    expect(buildSavedParam(["a/b", "c/d"])).toBe("a%2Fb,c%2Fd");
  });

  it("parseSavedSlugs와 왕복된다", () => {
    const slugs = ["morluto/rea", "owner/repo name", "a,b"];
    expect(parseSavedSlugs(buildSavedParam(slugs))).toEqual(slugs);
  });

  it("빈 목록은 빈 문자열", () => {
    expect(buildSavedParam([])).toBe("");
  });
});

describe("readSavedList / writeSavedList", () => {
  it("저장하지 않은 상태는 빈 목록", () => {
    expect(readSavedList(fakeStorage())).toEqual([]);
  });

  it("JSON 배열을 읽어 목록으로 돌려준다", () => {
    const storage = fakeStorage({
      [SAVED_STORAGE_KEY]: JSON.stringify([
        { slug: "a/b", n: "A", k: "skill", st: 10, sh: null, savedAt: 1 },
      ]),
    });
    expect(readSavedList(storage)).toEqual([
      { slug: "a/b", n: "A", k: "skill", st: 10, sh: null, savedAt: 1 },
    ]);
  });

  it("깨진 JSON·배열이 아닌 값은 빈 목록으로 안전하게 처리", () => {
    expect(readSavedList(fakeStorage({ [SAVED_STORAGE_KEY]: "{oops" }))).toEqual([]);
    expect(readSavedList(fakeStorage({ [SAVED_STORAGE_KEY]: '{"slug":"a"}' }))).toEqual([]);
    expect(readSavedList(null)).toEqual([]);
  });

  it("형식이 깨진 항목은 건너뛴다", () => {
    const storage = fakeStorage({
      [SAVED_STORAGE_KEY]: JSON.stringify([
        { slug: "a/b", n: "A", k: "skill", st: 10, sh: null, savedAt: 1 },
        { slug: 42 },
        null,
      ]),
    });
    expect(readSavedList(storage).map((e) => e.slug)).toEqual(["a/b"]);
  });

  it("쓰고 읽으면 그대로 돌아온다", () => {
    const storage = fakeStorage();
    const list: SavedEntry[] = [{ slug: "a/b", n: "A", k: "mcp", st: 5, sh: "요약", savedAt: 7 }];
    writeSavedList(storage, list);
    expect(storage.data[SAVED_STORAGE_KEY]).toBeTruthy();
    expect(readSavedList(storage)).toEqual(list);
  });

  it("저장소가 없으면 조용히 무시한다", () => {
    expect(() => writeSavedList(null, [])).not.toThrow();
  });
});

describe("toggleSaved / isSaved / mergeSaved", () => {
  it("저장되지 않은 항목은 맨 앞에 추가한다", () => {
    const list = toggleSaved([], entry("a/b"));
    expect(list.map((e) => e.slug)).toEqual(["a/b"]);
    expect(typeof list[0].savedAt).toBe("number");
  });

  it("저장된 항목을 다시 누르면 제거한다", () => {
    const once = toggleSaved([], entry("a/b"));
    const twice = toggleSaved(once, entry("a/b"));
    expect(twice).toEqual([]);
    expect(isSaved(twice, "a/b")).toBe(false);
  });

  it("isSaved은 슬러그로 판정한다", () => {
    const list = toggleSaved([], entry("a/b"));
    expect(isSaved(list, "a/b")).toBe(true);
    expect(isSaved(list, "c/d")).toBe(false);
  });

  it("mergeSaved는 중복 없이 합친다", () => {
    const mine = toggleSaved([], entry("a/b"));
    const merged = mergeSaved(mine, [
      { slug: "a/b", n: "A", k: "skill", st: 1, sh: null, savedAt: 2 },
      { slug: "c/d", n: "C", k: "mcp", st: 2, sh: null, savedAt: 3 },
    ]);
    expect(merged.map((e) => e.slug)).toEqual(["a/b", "c/d"]);
  });

  it("toSavedEntry는 랭킹 행을 저장 항목으로 바꾼다", () => {
    expect(toSavedEntry({ slug: "a/b", n: "A", k: "mcp", st: 42, sh: "요약" })).toEqual({
      slug: "a/b",
      n: "A",
      k: "mcp",
      st: 42,
      sh: "요약",
    });
  });
});
